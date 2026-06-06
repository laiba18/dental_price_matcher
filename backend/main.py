"""
main.py — FastAPI application and pipeline orchestrator.

Pipeline (simplified):
  1. extract      — PDF → line items (extractor.py)
  2. intelligence — parse + search + price in one combined layer (intelligence.py)
  3. match        — 4-criteria match scoring + equivalency (matcher.py)
  4. report       — 3 Excel output files (reporter.py)

No separate normaliser or scraper steps.
"""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import aiosqlite
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv

from backend.database import init_db, DB_PATH
from backend.layers.extractor import extract, hash_file
from backend.layers.intelligence import IntelligenceLayer
from backend.layers.matcher import MatcherLayer
from backend.layers.reporter import ReporterLayer

load_dotenv()

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

def _cors_origins() -> list[str]:
    origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5500",
        "null",
    ]
    primary = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000")
    if primary:
        origins.append(primary)
    extra = os.getenv("ALLOWED_ORIGINS", "")
    for origin in extra.split(","):
        origin = origin.strip()
        if origin:
            origins.append(origin)
    return list(dict.fromkeys(origins))


app = FastAPI(title="Dental Supply Price Intelligence", version="5.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"https://([a-z0-9-]+\.)*(vercel\.app|netlify\.app)$",
    allow_methods=["*"],
    allow_headers=["*"],
)

_jobs: dict[str, dict] = {}

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


async def _mark_order_failed(
    order_id: int | None,
    filename: str,
    file_hash: str,
    error_message: str,
) -> int | None:
    """Persist failed status so the order appears in history."""
    async with aiosqlite.connect(DB_PATH) as db:
        if order_id:
            await db.execute(
                "UPDATE orders SET status='failed', error_message=? WHERE id=?",
                (error_message, order_id),
            )
            await db.commit()
            return order_id

        cur = await db.execute(
            """INSERT INTO orders
               (filename, file_hash, status, error_message, item_count)
               VALUES (?, ?, 'failed', ?, 0)
               ON CONFLICT(file_hash) DO UPDATE SET
                 status='failed',
                 error_message=excluded.error_message,
                 created_at=datetime('now')""",
            (filename, file_hash, error_message),
        )
        await db.commit()
        if cur.lastrowid:
            return cur.lastrowid
        row = await db.execute_fetchall(
            "SELECT id FROM orders WHERE file_hash=?", (file_hash,)
        )
        return row[0][0] if row else None


def _fail_job(
    job_id: str,
    message: str,
    code: str = "PROCESSING_FAILED",
    order_id: int | None = None,
):
    emit_data: dict = {"message": message, "code": code}
    if order_id:
        emit_data["order_id"] = order_id
    _jobs[job_id]["events"].append({"event": "error", "data": emit_data, "ts": time.time()})
    _jobs[job_id]["status"] = "failed"
    _jobs[job_id]["error"] = message
    if order_id:
        _jobs[job_id]["order_id"] = order_id


@app.on_event("startup")
async def startup():
    await init_db()


async def run_pipeline(job_id: str, file_path: Path, original_filename: str):

    def emit(event: str, data: dict):
        _jobs[job_id]["events"].append({"event": event, "data": data, "ts": time.time()})

    order_id: int | None = None
    file_hash = hash_file(file_path)

    try:
        # ── Step 1: Extract PDF ───────────────────────────────────────────────
        emit("progress", {"step": 1, "pct": 5, "label": "Reading and extracting PDF..."})

        try:
            order = extract(file_path)
        except Exception as e:
            msg = f"PDF extraction failed: {e}"
            order_id = await _mark_order_failed(None, original_filename, file_hash, msg)
            _fail_job(job_id, msg, "PDF_EXTRACTION_FAILED", order_id)
            return

        if not order.line_items:
            msg = "No line items found. Please upload a valid Henry Schein order confirmation PDF."
            order_id = await _mark_order_failed(None, original_filename, file_hash, msg)
            _fail_job(job_id, msg, "NO_LINE_ITEMS", order_id)
            return
        total_label = f"${order.total_price:,.2f}" if order.total_price else "N/A"
        emit("progress", {
            "step": 1, "pct": 15,
            "label": (
                f"Extracted {len(order.line_items)} line items  ·  "
                f"Ref: {order.order_ref or 'N/A'}  ·  "
                f"Date: {order.order_date or 'N/A'}  ·  "
                f"Total: {total_label}"
            ),
        })

        # Save to DB
        async with aiosqlite.connect(DB_PATH) as db:
            existing = await db.execute_fetchall(
                "SELECT id FROM orders WHERE file_hash = ?", (file_hash,)
            )
            if existing:
                emit("warning", {"message": "File already processed — running again."})

            cur = await db.execute(
                """INSERT OR REPLACE INTO orders
                   (filename, file_hash, order_ref, order_date, patient_name,
                    total_price, item_count, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'processing')""",
                (original_filename, file_hash, order.order_ref, order.order_date,
                 order.patient_name, order.total_price, len(order.line_items)),
            )
            order_id = cur.lastrowid
            _jobs[job_id]["order_id"] = order_id

            for item in order.line_items:
                await db.execute(
                    """INSERT INTO line_items
                       (order_id, line_number, schein_sku, description_raw,
                        qty, uom, unit_price, ext_price)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (order_id, item.line_number, item.schein_sku,
                     item.description_raw, item.qty, item.uom,
                     item.unit_price, item.ext_price),
                )
            await db.commit()

        # ── Step 2: Intelligence (parse + search + price) ──────────────────────
        item_count = len(order.line_items)
        emit("progress", {
            "step": 2,
            "pct": 20,
            "label": f"Starting price search for {item_count} line items…",
            "item_index": 0,
            "item_total": item_count,
            "substep": "starting",
            "detail": (
                f"Each item will be parsed, searched on the web, and scraped for prices. "
                f"This step covers {item_count} products and usually takes the longest."
            ),
            "filename": original_filename,
            "order_ref": order.order_ref,
            "order_id": order_id,
            "order_date": order.order_date,
        })

        intel = IntelligenceLayer()
        order.line_items, raw_supplier_results, sweep_results, search_queries = await intel.process(
            order.line_items,
            emit=emit,
            order_meta={
                "filename": original_filename,
                "order_ref": order.order_ref,
                "order_id": order_id,
                "order_date": order.order_date,
            },
        )

        high_conf = sum(
            1 for it in order.line_items
            if it.description_parsed and it.description_parsed.parse_confidence >= 0.7
        )
        total_prices = sum(
            1 for v in raw_supplier_results.values()
            for r in v if r.price is not None
        )
        emit("progress", {
            "step": 2, "pct": 72,
            "label": (
                f"Done — {high_conf}/{len(order.line_items)} high-confidence parses  ·  "
                f"{total_prices} prices found"
            ),
        })

        # Update DB with parsed descriptions
        async with aiosqlite.connect(DB_PATH) as db:
            for item in order.line_items:
                pd = item.description_parsed
                if pd:
                    await db.execute(
                        """UPDATE line_items
                           SET description_parsed = ?, parse_confidence = ?, manufacturer_pn = ?
                           WHERE order_id = ? AND line_number = ?""",
                        (pd.model_dump_json(), pd.parse_confidence,
                         pd.manufacturer_part_number, order_id, item.line_number),
                    )
            await db.commit()

        # ── Step 3: Match + equivalency ───────────────────────────────────────
        emit("progress", {
            "step": 3, "pct": 75,
            "label": "Scoring matches and evaluating equivalencies...",
        })

        matcher = MatcherLayer()
        matched, actionable_equiv, borderline_equiv = await matcher.process(
            order.line_items, raw_supplier_results
        )

        exact_count = sum(
            1 for results in matched.values()
            for r in results if r.match_type == "exact" and r.price is not None
        )
        emit("progress", {
            "step": 3, "pct": 86,
            "label": (
                f"{exact_count} exact matches  ·  "
                f"{len(actionable_equiv)} equivalency recommendations  ·  "
                f"{len(borderline_equiv)} borderline"
            ),
        })

        # Save results to DB
        async with aiosqlite.connect(DB_PATH) as db:
            for item in order.line_items:
                rows = await db.execute_fetchall(
                    "SELECT id FROM line_items WHERE order_id=? AND line_number=?",
                    (order_id, item.line_number),
                )
                if not rows:
                    continue
                li_id = rows[0][0]

                for r in raw_supplier_results.get(item.line_number, []):
                    await db.execute(
                        """INSERT INTO price_results
                           (line_item_id, supplier, price, url, pack_qty, pack_unit,
                            pack_condition_note, match_type, match_confidence,
                            matched_brand, matched_product, matched_form, matched_pack,
                            match_reasoning, login_required, blocked, no_public_price,
                            raw_text, source)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (li_id, r.supplier, r.price, r.url, r.pack_qty, r.pack_unit,
                         r.pack_condition_note, r.match_type, r.match_confidence,
                         int(r.matched_brand), int(r.matched_product_name),
                         int(r.matched_form), int(r.matched_pack_qty),
                         r.match_reasoning, int(r.login_required),
                         int(r.blocked), int(r.no_public_price),
                         r.raw_text, r.source),
                    )
                for m in actionable_equiv + borderline_equiv:
                    if m.line_item_id == item.line_number:
                        await db.execute(
                            """INSERT INTO equivalency_matches
                               (line_item_id, schein_sku, schein_price, equiv_product,
                                equiv_brand, equiv_supplier, confidence, basis)
                               VALUES (?,?,?,?,?,?,?,?)""",
                            (li_id, m.schein_sku, m.schein_price, m.equiv_product,
                             m.equiv_brand, m.equiv_supplier, m.confidence, m.basis),
                        )
            await db.commit()

        # ── Step 4: Reports ───────────────────────────────────────────────────
        emit("progress", {"step": 4, "pct": 90, "label": "Generating 3 Excel reports..."})

        reporter = ReporterLayer()
        p1, p2, p3 = reporter.process(
            order, order.line_items, matched,
            sweep_results, raw_supplier_results,
            actionable_equiv, borderline_equiv,
            search_queries,
        )

        total_savings = 0.0
        equiv_ids = {m.line_item_id for m in actionable_equiv}
        for item in order.line_items:
            if item.line_number in equiv_ids:
                continue
            valid = [
                r for r in matched.get(item.line_number, [])
                if r.source == "web_search_exact"
                and r.match_type in ("exact", "pack_mismatch") and r.price
            ]
            if valid:
                best = min(valid, key=lambda r: r.price)
                saving = (item.unit_price - best.price) * item.qty
                if saving > 0:
                    total_savings += saving

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """UPDATE orders
                   SET status='complete',
                       output_price_match=?, output_alternate=?, output_evidence=?
                   WHERE id=?""",
                (p1.name, p2.name, p3.name, order_id),
            )
            await db.commit()

        result = {
            "order_id":               order_id,
            "order_ref":              order.order_ref,
            "order_date":             order.order_date,
            "patient_name":           order.patient_name,
            "line_items":             len(order.line_items),
            "high_conf_parses":       high_conf,
            "exact_matches":          exact_count,
            "equiv_recommendations":  len(actionable_equiv),
            "total_potential_savings": round(total_savings, 2),
            "output_price_match":     p1.name,
            "output_alternate":       p2.name,
            "output_evidence":        p3.name,
        }

        emit("complete", result)
        _jobs[job_id]["status"] = "complete"
        _jobs[job_id]["result"] = result

    except Exception as e:
        msg = f"Unexpected processing error: {e}"
        order_id = await _mark_order_failed(
            order_id, original_filename, file_hash, msg
        )
        _fail_job(job_id, msg, "UNEXPECTED_ERROR", order_id)


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="Only PDF files are accepted.")

    content = await file.read()
    if not content:
        raise HTTPException(400, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            400,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    if not content[:5].startswith(b"%PDF"):
        raise HTTPException(
            400,
            detail="Invalid or corrupted PDF file. Please upload a valid PDF document.",
        )

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "running", "events": [], "result": None, "order_id": None}
    save_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
    with open(save_path, "wb") as f:
        f.write(content)
    asyncio.create_task(run_pipeline(job_id, save_path, file.filename))
    return {"job_id": job_id, "filename": file.filename}


@app.get("/status/{job_id}")
async def stream_status(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")

    async def generate():
        last = 0
        while True:
            job = _jobs.get(job_id)
            if not job:
                break
            for ev in job["events"][last:]:
                yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'])}\n\n"
                last += 1
            if job["status"] in ("complete", "failed"):
                yield "event: done\ndata: {}\n\n"
                break
            await asyncio.sleep(0.3)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/result/{job_id}")
async def get_result(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    job = _jobs[job_id]
    if job["status"] != "complete":
        return {"status": job["status"]}
    return {"status": "complete", **job["result"]}


@app.get("/download/{filename}")
async def download_file(filename: str):
    if not filename.endswith(".xlsx"):
        raise HTTPException(400, "Invalid file type")
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@app.get("/history")
async def get_history():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT id, filename, order_ref, order_date, patient_name,
                      total_price, item_count, status, error_message,
                      output_price_match, output_alternate, output_evidence, created_at
               FROM orders ORDER BY created_at DESC LIMIT 50"""
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@app.get("/health")
async def health():
    return {"status": "ok", "version": "5.0.0"}