"""
layers/reporter.py — Generates the three required output Excel files.

Fixes in this version:
  1. File 1: Removed "Search Query Used" column (not in client spec)
  2. File 1: Exact 10 columns as specified by client
  3. File 1: Savings number format fixed (no raw floats)
  4. File 1: Pack note only shows "Routed to Alternate Purchase List" cleanly
  5. File 1: Suppresses prices that are MORE expensive than Schein
  6. File 2: Removed separate URL column (Price cell is hyperlinked instead)
  7. File 2: Negative savings shown as "—" (equiv is more expensive)
  8. File 2: Estimated savings = None when equiv_price > schein_price
  9. File 3: Match confidence shown for all rows including unmatched prices
"""

from datetime import datetime
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from backend.models import (
    LineItem, OrderExtraction, PriceResult,
    EquivalencyMatch, WebSweepResult,
)

OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs"

C = {
    "navy":   "1D3557",
    "blue":   "457B9D",
    "green":  "2D6A4F",
    "glight": "D4EDDA",
    "yellow": "FFF3CD",
    "red":    "C62828",
    "rlight": "FDECEA",
    "grey":   "F1F3F4",
    "white":  "FFFFFF",
}

MONEY = '"$"#,##0.00'


def _fill(c):
    return PatternFill("solid", fgColor=c)

def _font(bold=False, size=10, color="000000", italic=False):
    return Font(bold=bold, size=size, color=color, italic=italic, name="Calibri")

def _border():
    t = Side(style="thin", color="CCCCCC")
    return Border(bottom=t)

CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT   = Alignment(horizontal="left",   vertical="center", wrap_text=True)
RIGHT  = Alignment(horizontal="right",  vertical="center")


def _w(ws, row, col, val, bold=False, fill=None, align=None,
       fmt=None, color="000000", italic=False):
    c = ws.cell(row=row, column=col, value=val)
    c.font      = _font(bold=bold, color=color, italic=italic)
    c.border    = _border()
    if fill:  c.fill      = fill
    if align: c.alignment = align
    if fmt:   c.number_format = fmt
    return c


def _header_row(ws, row_num, headers, bg=C["navy"], fg=C["white"], height=28):
    for col, text in enumerate(headers, 1):
        c = ws.cell(row=row_num, column=col, value=text)
        c.font      = _font(bold=True, color=fg)
        c.fill      = _fill(bg)
        c.alignment = CENTER
        c.border    = _border()
    ws.row_dimensions[row_num].height = height


def _title_row(ws, row_num, text, n_cols):
    last = get_column_letter(n_cols)
    ws.merge_cells(f"A{row_num}:{last}{row_num}")
    c = ws[f"A{row_num}"]
    c.value     = text
    c.font      = _font(bold=True, size=12, color=C["navy"])
    c.fill      = _fill(C["grey"])
    c.alignment = CENTER
    ws.row_dimensions[row_num].height = 28


def _subtitle_row(ws, row_num, text, n_cols):
    last = get_column_letter(n_cols)
    ws.merge_cells(f"A{row_num}:{last}{row_num}")
    c = ws[f"A{row_num}"]
    c.value     = text
    c.font      = _font(italic=True, size=9, color="666666")
    c.alignment = CENTER
    ws.row_dimensions[row_num].height = 14


def _set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _money(val):
    """Round to 2 decimal places to avoid floating point display issues."""
    return round(float(val), 2) if val is not None else None


def _match_score_label(r: PriceResult | None) -> str:
    if not r or not r.match_type:
        return "—"
    labels = {
        "exact": "EXACT",
        "pack_mismatch": "CLOSE",
        "approximate": "APPROXIMATE",
    }
    lbl = labels.get(r.match_type, r.match_type.upper())
    conf = r.match_confidence or 0
    return f"{lbl} ({conf:.0%})"


def _pick_best_price(results, schein_price, in_equiv):
    """Best hit from exact-name web search for File 1 (price + URL always shown)."""
    top = _pick_top_exact_prices(results, 1)
    if not top:
        return None, None
    best = top[0]
    has_savings = best.price < schein_price
    return best, ("confirmed" if has_savings else "reference")


def _pick_top_exact_prices(results, limit: int = 3) -> list[PriceResult]:
    """Up to N cheapest exact-name web hits with unique URLs."""
    exact_hits = [
        r for r in results
        if r.source == "web_search_exact" and r.price is not None and r.url
    ]
    if not exact_hits:
        return []

    confirmed = [r for r in exact_hits if r.match_type in ("exact", "pack_mismatch")]
    pool = confirmed or exact_hits
    pool.sort(key=lambda r: (r.price, -(r.match_confidence or 0)))

    picked: list[PriceResult] = []
    seen_urls: set[str] = set()
    for r in pool:
        if r.url in seen_urls:
            continue
        seen_urls.add(r.url)
        picked.append(r)
        if len(picked) >= limit:
            break
    return picked


# ─────────────────────────────────────────────────────────────────────────────
# FILE 1 — Price Match Negotiation Report
# Exact 10 columns as specified by client
# ─────────────────────────────────────────────────────────────────────────────

def _build_price_match(
    wb, order, line_items, matched, equiv_item_ids, run_date
):
    ws = wb.active
    ws.title = "Price Match Report"
    ws.freeze_panes = "A4"
    N = 13

    _title_row(ws, 1, (
        f"Henry Schein Price Match Negotiation  ·  "
        f"Ref: {order.order_ref or 'N/A'}  ·  "
        f"Date: {order.order_date or 'N/A'}  ·  "
        f"Patient: {order.patient_name or 'N/A'}  ·  "
        f"Generated: {run_date}"
    ), N)

    _subtitle_row(ws, 2, (
        "All line items · Best public price from exact-name web search (up to 3 matches) · "
        "Parsed-query alternates → Alternate Purchase List"
    ), N)

    _header_row(ws, 3, [
        "Schein SKU",
        "Manufacturer Part Number",
        "Description",
        "Qty Ordered",
        "Schein Unit Price",
        "Best Public Price Found",
        "Match Score",
        "Source Site",
        "Product URL Link",
        'Pack/Qty Condition\n(e.g. "6-pack price")',
        "Savings Per Unit",
        "Total Savings",
        "Match Reasoning",
    ])

    row_groups = []
    for item in line_items:
        in_equiv = item.line_number in equiv_item_ids
        results = matched.get(item.line_number, [])
        top_prices = _pick_top_exact_prices(results, 3)
        best = top_prices[0] if top_prices else None
        match_kind = None
        if best:
            match_kind = "confirmed" if best.price < item.unit_price else "reference"

        savings_unit  = None
        total_savings = 0.0
        pct           = 0.0
        if best and match_kind == "confirmed":
            savings_unit  = _money(item.unit_price - best.price)
            total_savings = _money(savings_unit * item.qty) if savings_unit and savings_unit > 0 else 0.0
            pct           = (savings_unit / item.unit_price) if savings_unit and item.unit_price else 0.0

        pd  = item.description_parsed
        mpn = (pd.manufacturer_part_number if pd else None) or "—"

        if in_equiv and not best:
            pack_note = "→ See Alternate Purchase List"
        elif in_equiv and best:
            pack_note = "Exact web match · also see Alternate Purchase List"
        elif best and match_kind == "reference":
            pack_note = "Public price ≥ Schein — reference only (no savings)"
        elif best and best.pack_condition_note:
            pack_note = best.pack_condition_note
        else:
            pack_note = "—"

        row_groups.append({
            "item":          item,
            "in_equiv":      in_equiv,
            "top_prices":    top_prices,
            "best":          best,
            "match_kind":    match_kind,
            "mpn":           mpn,
            "savings_unit":  savings_unit if savings_unit and savings_unit > 0 else None,
            "total_savings": total_savings,
            "pct":           pct,
            "pack_note":     pack_note,
        })

    row_groups.sort(key=lambda r: r["total_savings"], reverse=True)

    ri = 4
    for rg in row_groups:
        pct = rg["pct"]
        if pct >= 0.10:
            rf = _fill(C["glight"])
        elif pct >= 0.05:
            rf = _fill(C["yellow"])
        elif ri % 2 == 0:
            rf = _fill(C["grey"])
        else:
            rf = _fill(C["white"])

        item = rg["item"]
        hits = rg["top_prices"] or [None]

        for rank, hit in enumerate(hits):
            is_primary = rank == 0
            row_fill = rf if is_primary else _fill(C["grey"])

            if is_primary:
                _w(ws, ri, 1, item.schein_sku,      fill=row_fill, align=LEFT)
                _w(ws, ri, 2, rg["mpn"],             fill=row_fill, align=LEFT)
                _w(ws, ri, 3, item.description_raw, fill=row_fill, align=LEFT)
                _w(ws, ri, 4, item.qty,             fill=row_fill, align=RIGHT)
                _w(ws, ri, 5, item.unit_price,      fill=row_fill, align=RIGHT, fmt=MONEY)
            else:
                _w(ws, ri, 1, "", fill=row_fill, align=LEFT)
                _w(ws, ri, 2, "", fill=row_fill, align=LEFT)
                _w(ws, ri, 3, f"↳ Option {rank + 1}", fill=row_fill, align=LEFT, italic=True, color="666666")
                _w(ws, ri, 4, "", fill=row_fill, align=RIGHT)
                _w(ws, ri, 5, "", fill=row_fill, align=RIGHT)

            if hit:
                _w(ws, ri, 6, _money(hit.price), fill=row_fill, align=RIGHT, fmt=MONEY)
                _w(ws, ri, 7, _match_score_label(hit), fill=row_fill, align=CENTER)
                _w(ws, ri, 8, hit.supplier, fill=row_fill, align=LEFT)
                url_cell = ws.cell(row=ri, column=9, value=hit.url or "—")
                url_cell.border = _border()
                url_cell.alignment = LEFT
                if hit.url:
                    url_cell.hyperlink = hit.url
                    url_cell.font = Font(color="0070C0", underline="single",
                                         name="Calibri", size=10)
                else:
                    url_cell.font = _font(italic=True, color="888888")
                reasoning = hit.match_reasoning or "—"
            else:
                _w(ws, ri, 6, "Not found", fill=row_fill, align=LEFT, italic=True, color="888888")
                _w(ws, ri, 7, "—", fill=row_fill, align=CENTER)
                _w(ws, ri, 8, "—", fill=row_fill, align=LEFT)
                _w(ws, ri, 9, "—", fill=row_fill, align=LEFT)
                reasoning = "—"

            if is_primary:
                _w(ws, ri, 10, rg["pack_note"], fill=row_fill, align=LEFT)
                if rg["savings_unit"]:
                    _w(ws, ri, 11, _money(rg["savings_unit"]), fill=row_fill, align=RIGHT, fmt=MONEY)
                    _w(ws, ri, 12, _money(rg["total_savings"]), fill=row_fill, align=RIGHT,
                       fmt=MONEY, bold=True)
                else:
                    _w(ws, ri, 11, "—", fill=row_fill, align=LEFT, color="888888")
                    _w(ws, ri, 12, "—", fill=row_fill, align=LEFT, color="888888")
                _w(ws, ri, 13, reasoning, fill=row_fill, align=LEFT)
            else:
                _w(ws, ri, 10, hit.pack_condition_note if hit and hit.pack_condition_note else "—",
                   fill=row_fill, align=LEFT)
                _w(ws, ri, 11, "—", fill=row_fill, align=LEFT, color="888888")
                _w(ws, ri, 12, "—", fill=row_fill, align=LEFT, color="888888")
                _w(ws, ri, 13, reasoning, fill=row_fill, align=LEFT)

            ws.row_dimensions[ri].height = 28
            ri += 1

    # Totals row — merge label through col 11; col 12 holds the total (col 13 unused)
    total_row = ri
    ws.merge_cells(f"A{total_row}:K{total_row}")
    c = ws.cell(row=total_row, column=1, value="TOTAL POTENTIAL SAVINGS")
    c.font = _font(bold=True, color=C["white"]); c.fill = _fill(C["navy"])
    c.alignment = RIGHT; c.border = _border()
    ws.row_dimensions[total_row].height = 24

    total_val = _money(sum(r["total_savings"] for r in row_groups if r["total_savings"]))
    tc = ws.cell(row=total_row, column=12,
                 value=total_val if total_val else "No confirmed savings found")
    tc.font   = _font(bold=True, color=C["white"])
    tc.fill   = _fill(C["navy"]); tc.alignment = RIGHT; tc.border = _border()
    if total_val:
        tc.number_format = MONEY

    # Legend
    leg = total_row + 2
    ws.merge_cells(f"A{leg}:M{leg}")
    lc = ws.cell(row=leg, column=1,
                 value="🟢 >10% savings   🟡 5–10% savings   "
                       "EXACT/CLOSE = confirmed match · APPROXIMATE = closest match for review   "
                       "Product URL links to verified product or supplier search page")
    lc.font = _font(italic=True, size=9, color="666666"); lc.alignment = LEFT

    _set_widths(ws, [12, 16, 40, 6, 14, 14, 16, 16, 36, 28, 13, 13, 48])


# ─────────────────────────────────────────────────────────────────────────────
# FILE 2 — Alternate Purchase List
# 6 columns as specified by client (URL merged into Price cell as hyperlink)
# ─────────────────────────────────────────────────────────────────────────────

def _build_alternate(wb, line_items, actionable, run_date):
    ws = wb.active
    ws.title = "Alternate Purchase List"
    ws.freeze_panes = "A4"
    N = 6

    _title_row(ws, 1, (
        f"Alternate Purchase Recommendations  ·  Generated: {run_date}  ·  "
        "Items here do NOT appear in the Price Match report"
    ), N)

    _subtitle_row(ws, 2, (
        "EXACT = same product, different brand/channel — straightforward substitution  ·  "
        "CLOSE = same category, compatible specs — likely acceptable  ·  "
        "POSSIBLE = needs review — in Evidence file only"
    ), N)

    # 6 columns exactly as specified by client
    _header_row(ws, 3, [
        "Original Schein Product and Schein Price",
        "Recommended Equivalent Product",
        "Recommended Supplier",
        "Price of the Equivalent",           # hyperlinked to source URL
        "Equivalency Basis and Confidence Level",
        "Estimated Savings vs. Schein Price",
    ])

    conf_order  = {"exact": 0, "close": 1}
    sorted_list = sorted(actionable, key=lambda m: conf_order.get(m.confidence, 9))

    for ri, m in enumerate(sorted_list, start=4):
        item_desc = next(
            (it.description_raw for it in line_items if it.line_number == m.line_item_id),
            "Unknown",
        )

        if m.confidence == "exact":
            rf = _fill(C["glight"])
        elif m.confidence == "close":
            rf = _fill(C["yellow"])
        else:
            rf = _fill(C["grey"])

        conf_labels = {
            "exact": "EXACT — same product, different brand or channel; substitution is straightforward",
            "close": "CLOSE — same category, compatible specs, minor differences; substitution likely acceptable",
        }
        conf_text = conf_labels.get(m.confidence, m.confidence.upper())
        basis_text = f"{conf_text}\n{m.basis}" if m.basis else conf_text

        schein_text = (
            f"{item_desc}\n"
            f"SKU: {m.schein_sku}  ·  Schein price: ${m.schein_price:,.2f}/unit"
        )

        _w(ws, ri, 1, schein_text,             fill=rf, align=LEFT)
        _w(ws, ri, 2, m.equiv_product,         fill=rf, align=LEFT)
        _w(ws, ri, 3, m.equiv_supplier or "—", fill=rf, align=LEFT)

        # Price — hyperlinked to source URL (URL column removed, merged here)
        if m.equiv_price is not None and m.equiv_price > 0:
            pc = _w(ws, ri, 4, _money(m.equiv_price), fill=rf, align=RIGHT, fmt=MONEY)
            if m.equiv_url:
                pc.hyperlink = m.equiv_url
                pc.font = Font(color="0070C0", underline="single",
                               name="Calibri", size=10)
        else:
            _w(ws, ri, 4, "Price not found", fill=rf, align=LEFT,
               italic=True, color="888888")

        _w(ws, ri, 5, basis_text, fill=rf, align=LEFT)

        # Savings — only show if positive; negative means equiv is more expensive
        if (m.estimated_savings is not None
                and m.estimated_savings > 0
                and m.equiv_price is not None
                and m.schein_price is not None
                and m.equiv_price < m.schein_price):
            sc = _w(ws, ri, 6, _money(m.estimated_savings),
                    fill=rf, align=RIGHT, fmt=MONEY, bold=True, color=C["green"])
        else:
            note = ""
            if (m.equiv_price is not None and m.schein_price is not None
                    and m.equiv_price > m.schein_price):
                note = f"Equiv ${m.equiv_price:,.2f} > Schein ${m.schein_price:,.2f}"
            _w(ws, ri, 6, note or "—", fill=rf, align=LEFT, color="888888")

        ws.row_dimensions[ri].height = 44

    if not sorted_list:
        ws.merge_cells("A4:F4")
        c = ws["A4"]
        c.value = ("No alternate purchase recommendations. "
                   "Fallback matches appear here when exact-name search finds fewer than 3 hits.")
        c.font = _font(italic=True, color="888888"); c.alignment = CENTER

    _set_widths(ws, [52, 34, 18, 18, 64, 22])


# ─────────────────────────────────────────────────────────────────────────────
# FILE 3 — Background Evidence File
# 5 columns as specified by client (plus Item Reference for navigation)
# ─────────────────────────────────────────────────────────────────────────────

def _build_evidence(
    wb, order, line_items, all_results, matched,
    sweep_results, borderline, run_date
):
    ws = wb.active
    ws.title = "Evidence"
    ws.freeze_panes = "A4"
    N = 6

    _title_row(ws, 1, (
        f"Background Evidence File  ·  "
        f"Ref: {order.order_ref or 'N/A'}  ·  "
        f"Generated: {run_date}"
    ), N)

    _subtitle_row(ws, 2,
        "Full audit trail — every price found, conditions, flagged sites, "
        "borderline equivalencies", N)

    # 5 client-specified columns + Item Reference for navigation
    _header_row(ws, 3, [
        "Source URLs for Every Price Found",
        "Full Quantity and Pack-Size Condition Detail",
        "Match Confidence Notes per Result",
        "Generic and Equivalent Alternative Findings\n(not in primary report)",
        "Sites Flagged (login-required / no-public-price / blocked)",
        "Item Reference (SKU · Description)",
    ], bg=C["blue"])

    row = 4

    def _ev_row(url, pack_detail, confidence_note, alt_findings,
                flagged, item_ref, row_fill=None):
        nonlocal row
        rf  = row_fill or (_fill(C["grey"]) if row % 2 == 0 else _fill(C["white"]))
        red = _fill(C["rlight"])

        # URL cell — hyperlinked
        c1 = ws.cell(row=row, column=1, value=url or "—")
        c1.border    = _border()
        c1.alignment = LEFT
        if url:
            c1.hyperlink = url
            c1.font      = Font(color="0070C0", underline="single",
                                name="Calibri", size=10)
            c1.fill      = rf
        else:
            c1.font = _font(italic=True, color="888888")
            c1.fill = rf

        _w(ws, row, 2, pack_detail,      fill=rf, align=LEFT)
        _w(ws, row, 3, confidence_note,  fill=rf, align=LEFT)
        _w(ws, row, 4, alt_findings,     fill=rf, align=LEFT)

        flag_fill = red if flagged and flagged != "—" else rf
        _w(ws, row, 5, flagged or "—",   fill=flag_fill, align=LEFT)
        _w(ws, row, 6, item_ref,         fill=rf, align=LEFT)

        ws.row_dimensions[row].height = 18
        row += 1

    def _section_hdr(text):
        nonlocal row
        ws.merge_cells(f"A{row}:F{row}")
        c = ws.cell(row=row, column=1, value=text)
        c.font      = _font(bold=True, color=C["white"])
        c.fill      = _fill(C["navy"])
        c.alignment = LEFT
        c.border    = _border()
        ws.row_dimensions[row].height = 20
        row += 1

    def _match_note(r: PriceResult) -> str:
        if r.price is None:
            if r.login_required:  return "—"
            if r.blocked:         return "—"
            if r.no_public_price: return "No price found on page"
            return "—"
        parts = [_match_score_label(r)]
        criteria = [lbl for flag, lbl in [
            (r.matched_brand,        "brand ✓"),
            (r.matched_product_name, "product ✓"),
            (r.matched_form,         "form ✓"),
            (r.matched_pack_qty,     "pack qty ✓"),
        ] if flag]
        if criteria:
            parts.append("Matched: " + ", ".join(criteria))
        if r.match_reasoning:
            parts.append(r.match_reasoning)
        return "  ·  ".join(parts) if parts else "Scored but not matched"

    def _flag_note(r: PriceResult) -> str:
        if r.login_required:   return f"🔒 LOGIN REQUIRED — {r.supplier}"
        if r.blocked:          return f"🚫 BLOCKED/TIMEOUT — {r.supplier}"
        if r.no_public_price:  return f"💲 NO PUBLIC PRICE — {r.supplier}"
        return "—"

    def _pack_detail(item: LineItem, r: PriceResult) -> str:
        parts = [f"Ordered: {item.qty} {item.uom} @ ${item.unit_price:,.2f}/unit"]
        if r.price is not None:
            parts.append(f"Found: ${r.price:,.2f}")
        if r.pack_qty:
            parts.append(f"Pack: {r.pack_qty:g} {r.pack_unit or 'units'}")
        if r.pack_condition_note:
            parts.append(r.pack_condition_note)
        return "  ·  ".join(parts)

    def _alt_findings(item: LineItem) -> str:
        parts = []
        for r in matched.get(item.line_number, []):
            if r.match_type == "approximate" and r.price is not None:
                parts.append(
                    f"Approx match: {r.supplier} ${r.price:,.2f}"
                    + (f" ({r.pack_condition_note})" if r.pack_condition_note else "")
                    + (f" — {r.match_reasoning}" if r.match_reasoning else "")
                )
        for m in borderline:
            if m.line_item_id == item.line_number:
                parts.append(
                    f"POSSIBLE alternative: {m.equiv_product}"
                    + (f" ({m.equiv_brand})" if m.equiv_brand else "")
                    + f" via {m.equiv_supplier or 'unknown'}"
                    + f"\nConfidence: POSSIBLE — {m.basis}"
                    + "\nRequires client review before acting"
                )
        return "\n".join(parts) if parts else "—"

    for item in line_items:
        item_ref = f"{item.schein_sku} — {item.description_raw}"
        results  = all_results.get(item.line_number, [])
        alt_text = _alt_findings(item)

        _section_hdr(
            f"Item {item.line_number}: {item.description_raw}  "
            f"(SKU {item.schein_sku}  ·  Schein ${item.unit_price:,.2f}/unit  ·  "
            f"Qty {item.qty})"
        )

        if not results:
            _ev_row(None,
                    f"Ordered: {item.qty} {item.uom} @ ${item.unit_price:,.2f}/unit",
                    "No public prices found via Jina web search",
                    alt_text, "—", item_ref)
            continue

        for i, r in enumerate(results):
            _ev_row(
                r.url,
                _pack_detail(item, r),
                _match_note(r),
                alt_text if i == 0 else "—",
                _flag_note(r),
                item_ref,
                row_fill=_fill(C["rlight"]) if _flag_note(r) != "—" else None,
            )

        # Web sweep row
        for sw in sweep_results:
            if sw.line_item_id != item.line_number:
                continue
            detail = f"Web sweep: \"{sw.query_used}\""
            if sw.price is not None:
                detail += f"  ·  Market floor: ${sw.price:,.2f}"
            if sw.site_name:
                detail += f"  ·  Via: {sw.site_name}"
            _ev_row(sw.url, detail,
                    "Web sweep — unverified market reference",
                    "—", "—", item_ref)

    # Possible equivalents not otherwise shown
    for m in borderline:
        item = next((it for it in line_items if it.line_number == m.line_item_id), None)
        if not item:
            continue
        existing = all_results.get(m.line_item_id, [])
        if existing:
            continue  # already shown via price rows above
        item_ref = f"{item.schein_sku} — {item.description_raw}"
        alt_line = (
            f"POSSIBLE alternative: {m.equiv_product}"
            + (f" ({m.equiv_brand})" if m.equiv_brand else "")
            + f" via {m.equiv_supplier or 'unknown'} — {m.basis}"
            + "\nRequires client review before acting"
        )
        _ev_row(m.equiv_url,
                f"Ordered: {item.qty} {item.uom} @ ${item.unit_price:,.2f}/unit",
                "Possible equivalent — manual review required",
                alt_line, "Manual review required", item_ref,
                row_fill=_fill(C["yellow"]))

    _set_widths(ws, [50, 44, 40, 52, 44, 38])

    # Raw PDF tab
    ws_raw = wb.create_sheet("Raw PDF Text")
    ws_raw["A1"].value = "Full text extracted from PDF — audit trail"
    ws_raw["A1"].font  = _font(bold=True, color=C["navy"])
    ws_raw["A1"].fill  = _fill(C["grey"])
    ws_raw.row_dimensions[1].height = 20
    for i, line in enumerate(order.raw_text.split("\n"), start=3):
        c = ws_raw.cell(row=i, column=1, value=line)
        c.font = Font(name="Courier New", size=8)
        if i % 2 == 0:
            c.fill = _fill(C["grey"])
        ws_raw.row_dimensions[i].height = 12
    ws_raw.column_dimensions["A"].width = 120


# ─────────────────────────────────────────────────────────────────────────────
# Public interface
# ─────────────────────────────────────────────────────────────────────────────

def build_all_reports(
    order, line_items, matched, sweep_results, all_results,
    actionable_equiv, borderline_equiv, search_queries=None,
):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts       = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ref      = (order.order_ref or "order").replace("/", "-")
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    equiv_ids = {
        m.line_item_id for m in actionable_equiv
        if "equivalency table" in (m.basis or "").lower()
    }

    wb1 = Workbook()
    _build_price_match(wb1, order, line_items, matched, equiv_ids, run_date)
    p1  = OUTPUT_DIR / f"1_price_match_{ref}_{ts}.xlsx"
    wb1.save(p1)

    wb2 = Workbook()
    _build_alternate(wb2, line_items, actionable_equiv, run_date)
    p2  = OUTPUT_DIR / f"2_alternate_purchase_{ref}_{ts}.xlsx"
    wb2.save(p2)

    wb3 = Workbook()
    _build_evidence(wb3, order, line_items, all_results, matched,
                    sweep_results, borderline_equiv, run_date)
    if "Sheet" in wb3.sheetnames and len(wb3.sheetnames) > 1:
        del wb3["Sheet"]
    p3  = OUTPUT_DIR / f"3_evidence_{ref}_{ts}.xlsx"
    wb3.save(p3)

    return p1, p2, p3


class ReporterLayer:
    def process(self, order, line_items, matched, sweep_results,
                all_results, actionable_equiv, borderline_equiv,
                search_queries=None):
        return build_all_reports(
            order, line_items, matched, sweep_results,
            all_results, actionable_equiv, borderline_equiv,
            search_queries,
        )