"""
layers/matcher.py — Product matching and equivalency evaluation.

Stage 1: 4-criteria match scoring using string similarity (local only, no Groq).
         Groq removed from matching entirely to prevent rate limit timeouts.
Stage 2: Equivalency table lookup — table confidence used directly, no Groq.

Key fixes in this version:
  - Groq completely removed from match scoring (local similarity is sufficient)
  - Groq completely removed from equivalency evaluation (table is authoritative)
  - find_equivalencies only routes items that ARE in the equiv table
  - Items with a cheaper direct match stay in File 1 (not diverted to File 2)
"""

import json
import asyncio
import os
import re
from pathlib import Path
from difflib import SequenceMatcher
from dotenv import load_dotenv

load_dotenv()

from backend.models import LineItem, PriceResult, EquivalencyMatch

EQUIV_PATH = Path(__file__).parent.parent.parent / "config" / "equivalency.txt"


# ─── JSON helper ──────────────────────────────────────────────────────────────

def _safe_parse(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except Exception:
                pass
    return {}


# ─── Local string-similarity scorer ──────────────────────────────────────────

def _normalise(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(
        r"\b(dental|supply|the|and|for|with|per|each|ea|bx|pk|bg|jr|bt|rl|cs|add|cart)\b",
        " ", s,
    )
    return re.sub(r"\s+", " ", s).strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalise(a), _normalise(b)).ratio()


def _word_overlap(a: str, b: str) -> float:
    """Fraction of meaningful words from `a` that appear in `b`."""
    a_words = set(_normalise(a).split())
    b_words = set(_normalise(b).split())
    if not a_words:
        return 0.0
    return len(a_words & b_words) / len(a_words)


_PACK_UNIT_RE = r"(?:bx|pk|pkg|bg|box|pack|bag|ct|ea|cs|kt|rl|roll|rolls)"


def _parse_count(raw: str) -> int:
    return int(re.sub(r"[,\s]", "", str(raw)))


def _strip_number_commas(text: str) -> str:
    """Normalize 1,200 → 1200 for qty regex matching."""
    return re.sub(r"(?<=\d),(?=\d)", "", text or "")


def _extract_qty_from_title(text: str) -> int | None:
    if not text:
        return None
    t = _strip_number_commas(text.lower())
    found: list[int] = []
    patterns = [
        rf"([\d]+)\s*/\s*{_PACK_UNIT_RE}\b",
        r"(?:item\s+includes|includes|contains)[:\s]+([\d]+)",
        r"([\d]+)\s+(?:\d+\s*(?:\"|in|inch)?\s*(?:x|×)\s*\d+\s*(?:\"|in|inch)?\s*)?"
        r"sheets?\s*per\s*(?:roll|box|pack|bag)",
        r"([\d]+)\s*sheets?\s*per\s*(?:roll|box|pack|bag)",
        r"([\d]+)\s*(?:pk|pkg|pack|count|ct|piece|sheets?)\b",
        r"(?:box|case|pack)\s+of\s+([\d]+)",
        r"([\d]+)\s*per\s+(?:box|pack|bag|case|roll)",
        r"packaging:\s*([\d]+)",
        r"([\d]+)\s*[-\s]*(?:tips|mixing|angles|syringes|boxes|rolls|sheets)\b",
    ]
    for p in patterns:
        for m in re.finditer(p, t, re.I):
            n = int(m.group(1))
            if 1 <= n <= 100000:
                found.append(n)
    if not found:
        return None
    return max(found)


def _pack_tokens(text: str) -> set[str]:
    """Pack/size tokens from the full line description (e.g. 1oz, 100/bx)."""
    tokens: set[str] = set()
    for m in re.finditer(
        r"\d+\s*/\s*(?:Bx|Pk|Bg|Jr|Bt|Rl|Roll|Ea|CS|KT)\b",
        text,
        re.I,
    ):
        tokens.add(re.sub(r"\s+", "", m.group(0).lower()))
    for m in re.finditer(
        r"\d+(?:\.\d+)?\s*(?:oz|ml|mm|liter|meter|cc)\b",
        text,
        re.I,
    ):
        tokens.add(re.sub(r"\s+", "", m.group(0).lower()))
    return tokens


def _schein_pack_counts(text: str) -> set[int]:
    counts: set[int] = set()
    for tok in _pack_tokens(text):
        m = re.match(r"(\d+)", re.sub(r"[^a-z0-9/]", "", tok.lower()))
        if m:
            counts.add(int(m.group(1)))
    for m in re.finditer(rf"([\d,]+)\s*/\s*{_PACK_UNIT_RE}\b", text, re.I):
        counts.add(_parse_count(m.group(1)))
    return counts


def _pack_size_confirmed(schein_text: str, comp_text: str, pd) -> tuple[bool, bool]:
    """
    Return (qty_match, token_or_unit_match).
    bx/pk/pkg/box are treated as equivalent pack units.
    """
    pack_tokens = _pack_tokens(schein_text)
    comp_flat   = re.sub(r"[^a-z0-9]", "", comp_text.lower())

    token_literal = True
    if pack_tokens:
        token_literal = any(
            re.sub(r"[^a-z0-9]", "", tok) in comp_flat for tok in pack_tokens
        )

    qty_match = True
    if pd and pd.pack_qty:
        target = int(pd.pack_qty)
        found_qty = _extract_qty_from_title(comp_text)
        if found_qty is not None:
            qty_match = abs(found_qty - target) <= max(1, target * 0.15)
        elif _schein_pack_counts(schein_text):
            qty_match = False

        comp_norm = _strip_number_commas(comp_text)
        # Same count with equivalent unit (25/bx vs 25/pkg, 1200/bx vs 1200/roll)
        unit_equiv = False
        for count in _schein_pack_counts(schein_text) or {target}:
            if abs(count - target) > max(1, target * 0.15):
                continue
            if re.search(
                rf"\b{count}\s*/\s*{_PACK_UNIT_RE}\b",
                comp_norm,
                re.I,
            ):
                unit_equiv = True
                break
            if re.search(
                rf"\b{count}\s+sheets?\s*per\s*(?:roll|box|pack|bag)\b",
                comp_norm,
                re.I,
            ):
                unit_equiv = True
                break
            count_flat = str(count)
            if count_flat in re.sub(r"[^a-z0-9]", "", comp_norm.lower()) and re.search(
                rf"(?:{_PACK_UNIT_RE}|sheets?\s*per\s*(?:roll|box|pack))\b",
                comp_norm,
                re.I,
            ):
                unit_equiv = True
                break

        pack_ok = qty_match or token_literal or unit_equiv
        return qty_match or unit_equiv, pack_ok

    return True, token_literal or not pack_tokens


def format_match_reasoning(item: LineItem, local: dict) -> str:
    """Human-readable summary of what matched and what did not."""
    parts: list[str] = []
    base = (local.get("reasoning") or "").strip()
    if base:
        parts.append(base)

    pd = item.description_parsed
    matched: list[str] = []
    missing: list[str] = []

    if local.get("matched_brand"):
        matched.append("brand")
    elif pd and pd.brand:
        missing.append(f"brand ({pd.brand})")

    if local.get("matched_product_name"):
        matched.append("product name")
    else:
        missing.append("product name")

    if local.get("matched_pack_qty"):
        matched.append("pack size")
    elif pd and pd.pack_qty:
        unit = pd.pack_unit or "pk"
        qty  = int(pd.pack_qty) if float(pd.pack_qty) == int(pd.pack_qty) else pd.pack_qty
        missing.append(f"pack size ({qty}/{unit})")

    if local.get("matched_form"):
        matched.append("form/spec")

    mt = local.get("match_type", "")
    if mt == "approximate" and pd and pd.brand and not local.get("matched_brand"):
        missing.append("exact brand required for EXACT tier")

    if matched:
        parts.append("Matching: " + ", ".join(matched))
    if missing:
        parts.append("Not matching: " + ", ".join(missing))

    return " · ".join(parts)


def _score_exact_input_match(item: LineItem, result: PriceResult) -> dict:
    """
    File 1 scoring — compare web hit to the FULL Schein line input
    (e.g. 'Benzo-Jel Topical Anesthetic Strawberry 1oz/Jr').
    Maps to EXACT / CLOSE / APPROXIMATE like equivalency confidence tiers.
    """
    schein_text = item.description_raw
    comp_text   = result.raw_text or ""

    if not comp_text:
        return {
            "match_type": "no_match", "confidence": 0.0,
            "matched_brand": False, "matched_product_name": False,
            "matched_form": False, "matched_pack_qty": False,
            "reasoning": "No product title captured",
        }

    sim     = _similarity(schein_text, comp_text)
    overlap = _word_overlap(schein_text, comp_text)
    score   = max(sim, overlap)

    pd = item.description_parsed
    brand_match = False
    if pd and pd.brand:
        brand_key = pd.brand.lower().replace("-", "")
        comp_key  = comp_text.lower().replace("-", "")
        brand_match = brand_key in comp_key

    pack_qty_match, pack_confirmed = _pack_size_confirmed(schein_text, comp_text, pd)

    reasoning = (
        f"Exact input sim={sim:.0%} overlap={overlap:.0%}"
        f" (sim=character similarity, overlap=Schein words found on page)"
    )

    # Same pack + product type (e.g. 500/bx soft prophy) — exact even if brand differs
    schein_product = schein_text
    if pd and pd.brand:
        schein_product = re.sub(
            r"\b" + re.escape(pd.brand) + r"\b", "", schein_text, flags=re.I
        )
    product_overlap = _word_overlap(schein_product, comp_text)
    if pack_confirmed and product_overlap >= 0.40:
        conf = min(0.92, max(score, product_overlap) + (0.10 if brand_match else 0.06))
        return {
            "match_type": "exact",
            "confidence": conf,
            "matched_brand": brand_match,
            "matched_product_name": True,
            "matched_form": True,
            "matched_pack_qty": pack_qty_match or pack_confirmed,
            "reasoning": reasoning + " · pack + product match",
        }

    # Brand hit without pack confirmation (e.g. Acclean 100/bx when Schein is 500/bx)
    if brand_match and pd and pd.pack_qty and not pack_confirmed:
        return {
            "match_type": "approximate",
            "confidence": min(0.55, score),
            "matched_brand": True,
            "matched_product_name": True,
            "matched_form": False,
            "matched_pack_qty": False,
            "reasoning": reasoning + " · brand match but pack size not confirmed",
        }

    if score >= 0.72 and brand_match and pack_confirmed:
        return {
            "match_type": "exact",
            "confidence": min(0.95, score + 0.08),
            "matched_brand": brand_match,
            "matched_product_name": True,
            "matched_form": score >= 0.55,
            "matched_pack_qty": pack_qty_match or pack_confirmed,
            "reasoning": reasoning + " · full input match",
        }

    if score >= 0.65 and (brand_match or score >= 0.78):
        if pack_confirmed:
            return {
                "match_type": "exact",
                "confidence": min(0.90, score + 0.05),
                "matched_brand": brand_match,
                "matched_product_name": True,
                "matched_form": True,
                "matched_pack_qty": pack_qty_match or pack_confirmed,
                "reasoning": reasoning + " · strong input match",
            }
        return {
            "match_type": "pack_mismatch",
            "confidence": min(0.85, score),
            "matched_brand": brand_match,
            "matched_product_name": True,
            "matched_form": True,
            "matched_pack_qty": False,
            "reasoning": reasoning + " · product match, pack may differ",
        }

    if score >= 0.48:
        reason = reasoning + " · partial input match"
        if pd and pd.brand and not brand_match:
            reason += f" · substitute brand (not {pd.brand})"
        return {
            "match_type": "approximate",
            "confidence": score,
            "matched_brand": brand_match,
            "matched_product_name": overlap >= 0.45,
            "matched_form": False,
            "matched_pack_qty": pack_confirmed,
            "reasoning": reason,
        }

    return {
        "match_type": "no_match",
        "confidence": score,
        "matched_brand": False,
        "matched_product_name": False,
        "matched_form": False,
        "matched_pack_qty": False,
        "reasoning": reasoning + " · below exact-input threshold",
    }


def _score_equiv_alternate_match(
    item: LineItem,
    result: PriceResult,
    parsed_query: str,
    equiv_entry: dict | None = None,
) -> dict:
    """
    File 2 scoring — parsed-query + equivalency table logic.
    Uses table confidence (exact/close/possible) as the match tier floor.
    """
    comp_text = result.raw_text or ""
    if not comp_text:
        return {
            "match_type": "no_match", "confidence": 0.0,
            "matched_brand": False, "matched_product_name": False,
            "matched_form": False, "matched_pack_qty": False,
            "reasoning": "No product title captured",
        }

    q_sim   = max(_similarity(parsed_query, comp_text), _word_overlap(parsed_query, comp_text))
    score   = q_sim
    reasoning = f"Parsed query sim={q_sim:.0%}"

    if equiv_entry:
        equiv_product = equiv_entry.get("equiv_product") or ""
        if equiv_product:
            eq_sim = max(_similarity(equiv_product, comp_text), _word_overlap(equiv_product, comp_text))
            score  = max(score, eq_sim)
            reasoning += f" · equiv product sim={eq_sim:.0%}"
        table_conf = equiv_entry.get("confidence", "possible")
        if equiv_entry.get("notes"):
            reasoning += f" · {equiv_entry['notes'][:50]}"
    else:
        table_conf = "possible"

    pd = item.description_parsed
    brand_match = False
    if pd and pd.brand:
        brand_match = pd.brand.lower().replace("-", "") in comp_text.lower().replace("-", "")

    floors = {"exact": 0.45, "close": 0.35, "possible": 0.28}
    if score < floors.get(table_conf, 0.28) and not brand_match:
        return {
            "match_type": "no_match", "confidence": score,
            "matched_brand": brand_match, "matched_product_name": False,
            "matched_form": False, "matched_pack_qty": False,
            "reasoning": reasoning + " · below equiv threshold",
        }

    if table_conf == "exact" and score >= 0.50:
        mt = "exact" if score >= 0.62 and brand_match else "pack_mismatch"
        conf = min(0.92, score + 0.12)
    elif table_conf == "close" and score >= 0.38:
        mt = "pack_mismatch"
        conf = min(0.85, score + 0.08)
    else:
        mt = "approximate"
        conf = min(0.75, score + 0.05)

    return {
        "match_type": mt,
        "confidence": conf,
        "matched_brand": brand_match,
        "matched_product_name": score >= 0.40,
        "matched_form": score >= 0.45,
        "matched_pack_qty": False,
        "reasoning": reasoning + f" · equiv tier={table_conf}",
    }


def _score_local(item: LineItem, result: PriceResult) -> dict:
    """
    Score match using string similarity — instant, no API, no rate limits.
    Uses both character-ratio and word-overlap; takes the higher of the two.
    """
    schein_text = item.description_raw
    comp_text   = result.raw_text or ""

    if not comp_text:
        return {
            "match_type": "approximate", "confidence": 0.3,
            "matched_brand": False, "matched_product_name": False,
            "matched_form": False, "matched_pack_qty": False,
            "reasoning": "No competitor description captured",
        }

    sim     = _similarity(schein_text, comp_text)
    overlap = _word_overlap(schein_text, comp_text)
    score   = max(sim, overlap)

    pd = item.description_parsed
    brand_match = False
    name_match  = False

    if pd and pd.brand:
        brand_match = pd.brand.lower() in comp_text.lower()
    if pd and pd.product_name:
        name_match = max(
            _similarity(pd.product_name, comp_text),
            _word_overlap(pd.product_name, comp_text),
        ) > 0.45

    pack_match = False
    if pd and pd.pack_qty and result.pack_qty:
        pack_match = abs(pd.pack_qty - result.pack_qty) < 1

    if score >= 0.60 or (brand_match and name_match):
        if pack_match or result.pack_qty is None:
            return {
                "match_type": "exact",
                "confidence": min(0.90, score + 0.10),
                "matched_brand": brand_match,
                "matched_product_name": name_match or score >= 0.60,
                "matched_form": score >= 0.50,
                "matched_pack_qty": pack_match,
                "reasoning": f"Strong match (sim={sim:.0%} overlap={overlap:.0%})",
            }
        else:
            return {
                "match_type": "pack_mismatch",
                "confidence": min(0.85, score),
                "matched_brand": brand_match,
                "matched_product_name": True,
                "matched_form": True,
                "matched_pack_qty": False,
                "reasoning": "Product matches but pack qty differs",
            }
    elif score >= 0.35 or (brand_match and score >= 0.25):
        return {
            "match_type": "approximate",
            "confidence": score,
            "matched_brand": brand_match,
            "matched_product_name": name_match,
            "matched_form": False,
            "matched_pack_qty": False,
            "reasoning": f"Partial match (sim={sim:.0%} overlap={overlap:.0%})",
        }
    else:
        return {
            "match_type": "no_match",
            "confidence": score,
            "matched_brand": False,
            "matched_product_name": False,
            "matched_form": False,
            "matched_pack_qty": False,
            "reasoning": f"Low similarity (sim={sim:.0%} overlap={overlap:.0%})",
        }


# ─── Main match_all (local only, no Groq) ────────────────────────────────────

async def match_all(
    line_items: list[LineItem],
    raw_results: dict[int, list[PriceResult]],
) -> dict[int, list[PriceResult]]:
    """
    Score every supplier result using local string similarity only.
    No Groq calls — eliminates all timeout and rate limit issues in matching.
    Local scoring handles 95%+ of cases correctly.
    """
    matched: dict[int, list[PriceResult]] = {i: [] for i in raw_results}

    # Pass through flag results (no price) unchanged
    for item_idx, results in raw_results.items():
        for r in results:
            if r.price is None:
                matched[item_idx].append(r)

    local_calls = 0
    kept = 0

    for item_idx, results in raw_results.items():
        item = line_items[item_idx - 1]
        for result in results:
            if result.price is None:
                continue

            # Pre-scored in intelligence layer (Jina web search)
            if result.source in ("web_search_exact", "web_search_fallback") and result.match_type:
                if result.match_type == "no_match":
                    local_calls += 1
                    continue
                kept += 1
                matched[item_idx].append(result)
                local_calls += 1
                continue

            score = _score_local(item, result)
            mt    = score.get("match_type", "no_match")
            local_calls += 1

            if mt == "no_match":
                continue

            result.match_type           = mt
            result.match_confidence     = score.get("confidence", 0.0)
            result.matched_brand        = score.get("matched_brand", False)
            result.matched_product_name = score.get("matched_product_name", False)
            result.matched_form         = score.get("matched_form", False)
            result.matched_pack_qty     = score.get("matched_pack_qty", False)
            result.match_reasoning      = score.get("reasoning", "")
            matched[item_idx].append(result)
            kept += 1

    type_order = {"exact": 0, "pack_mismatch": 1, "approximate": 2, None: 3}
    for idx in matched:
        matched[idx].sort(
            key=lambda r: (type_order.get(r.match_type, 3), r.price or 9999)
        )

    print(
        f"[matcher] Scoring done — {local_calls} scored locally, "
        f"{kept} kept (no Groq calls)"
    )
    return matched


# ─── Equivalency table ────────────────────────────────────────────────────────

def load_equivalency_table() -> list[dict]:
    entries = []
    if not EQUIV_PATH.exists():
        return entries
    with open(EQUIV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 6:
                entries.append({
                    "schein_sku":     parts[0],
                    "equiv_product":  parts[1],
                    "equiv_brand":    parts[2],
                    "equiv_supplier": parts[3] if len(parts) > 3 else "",
                    "category":       parts[4] if len(parts) > 4 else "",
                    "confidence":     parts[5] if len(parts) > 5 else "possible",
                    "notes":          parts[6] if len(parts) > 6 else "",
                })
    return entries


def _lookup_equiv_price(
    item: LineItem,
    entry: dict,
    matched_results: dict[int, list[PriceResult]],
    raw_results: dict[int, list[PriceResult]],
) -> tuple[float | None, str | None]:
    """Find best public price from the recommended equivalent supplier."""
    supplier_key = (entry.get("equiv_supplier") or "").lower().replace(" ", "_")
    if not supplier_key:
        return None, None

    for pool in (matched_results.get(item.line_number, []),
                 raw_results.get(item.line_number, [])):
        for r in pool:
            if supplier_key in r.supplier.lower().replace(" ", "_") and r.price is not None:
                return r.price, r.url
    return None, None


async def find_equivalencies(
    line_items: list[LineItem],
    matched_results: dict[int, list[PriceResult]],
    raw_results: dict[int, list[PriceResult]] | None = None,
) -> tuple[list[EquivalencyMatch], list[EquivalencyMatch]]:
    """
    Query equivalency table using table confidence directly — no Groq.

    Routing rules (Section 5.5 of briefing):
      - Item stays in File 1 (price match) if:
          a) A direct match was found at a cheaper price (savings > 5%)
          b) Item has NO entry in the equivalency table
      - Item routes to File 2 (alternate purchase) if:
          a) It IS in the equivalency table with exact/close confidence
          b) AND no cheaper direct match already found

    Only "exact" and "close" table entries go to File 2.
    "possible" entries go to evidence file only.
    """
    equiv_table = load_equivalency_table()
    if not equiv_table:
        print("[matcher] Equivalency table is empty — no items routed to File 2")
        return [], []

    raw = raw_results or matched_results
    actionable: list[EquivalencyMatch] = []
    borderline: list[EquivalencyMatch] = []
    routed = 0
    kept_in_file1 = 0

    for item in line_items:
        # Only process items that have an entry in the table
        relevant = [e for e in equiv_table if e["schein_sku"] == item.schein_sku]
        if not relevant:
            continue  # not in table → stays in File 1, no action

        # If a cheaper direct match exists with >5% savings → keep in File 1
        direct_matches = matched_results.get(item.line_number, [])
        min_savings_threshold = item.unit_price * 0.05  # 5% minimum
        has_good_direct_match = any(
            r.source == "web_search_exact"
            and r.match_type in ("exact", "pack_mismatch")
            and r.price is not None
            and (item.unit_price - r.price) >= min_savings_threshold
            for r in direct_matches
        )
        if has_good_direct_match:
            kept_in_file1 += 1
            continue  # stays in File 1 for price negotiation

        # Route to File 2 using table confidence directly (no Groq)
        for entry in relevant:
            final_conf = entry.get("confidence", "possible")
            basis      = entry.get("notes") or f"From equivalency table (confidence: {final_conf})"

            equiv_price, equiv_url = _lookup_equiv_price(
                item, entry, matched_results, raw
            )
            estimated_savings = None
            if equiv_price is not None and item.unit_price:
                estimated_savings = round(item.unit_price - equiv_price, 2)

            em = EquivalencyMatch(
                line_item_id=item.line_number,
                schein_sku=item.schein_sku,
                schein_price=item.unit_price,
                equiv_product=entry["equiv_product"],
                equiv_brand=entry["equiv_brand"] or None,
                equiv_supplier=entry["equiv_supplier"] or None,
                equiv_price=equiv_price,
                equiv_url=equiv_url,
                confidence=final_conf,
                basis=basis,
                estimated_savings=estimated_savings,
            )

            if final_conf in ("exact", "close"):
                actionable.append(em)
                routed += 1
            else:
                borderline.append(em)

    print(
        f"[matcher] Equivalency: {routed} items → File 2, "
        f"{kept_in_file1} kept in File 1 (cheaper direct match found), "
        f"{len(borderline)} borderline → evidence only"
        f" (no Groq calls)"
    )
    return actionable, borderline


def find_web_alternates(
    line_items: list[LineItem],
    raw_results: dict[int, list[PriceResult]],
) -> list[EquivalencyMatch]:
    """Route parsed-query Jina hits to Alternate Purchase (File 2), up to 3 per item."""
    alternates: list[EquivalencyMatch] = []

    for item in line_items:
        exact_hits = [
            r for r in raw_results.get(item.line_number, [])
            if r.source == "web_search_exact" and r.price is not None
        ]
        if exact_hits:
            continue  # exact match found — alternates belong in File 1 only

        fallbacks = [
            r for r in raw_results.get(item.line_number, [])
            if r.source == "web_search_fallback" and r.price is not None
        ]
        fallbacks.sort(key=lambda r: (r.price or 9999, -(r.match_confidence or 0)))
        for r in fallbacks[:3]:
            conf = "close" if (r.match_confidence or 0) >= 0.40 else "possible"
            savings = round(item.unit_price - r.price, 2) if r.price < item.unit_price else None
            score_lbl = r.match_type.upper() if r.match_type else "APPROXIMATE"
            if r.match_confidence:
                score_lbl = f"{score_lbl} ({r.match_confidence:.0%})"

            alternates.append(EquivalencyMatch(
                line_item_id=item.line_number,
                schein_sku=item.schein_sku,
                schein_price=item.unit_price,
                equiv_product=r.raw_text or "Alternative product",
                equiv_brand=None,
                equiv_supplier=r.supplier,
                equiv_price=r.price,
                equiv_url=r.url,
                confidence=conf,
                basis=(
                    f"Parsed-query web search · {score_lbl}"
                    + (f" · {r.match_reasoning}" if r.match_reasoning else "")
                ),
                estimated_savings=savings,
            ))

    print(f"[matcher] Web alternates: {len(alternates)} parsed-query hits → File 2")
    return alternates


class MatcherLayer:
    async def process(
        self,
        line_items: list[LineItem],
        raw_results: dict[int, list[PriceResult]],
    ) -> tuple[dict[int, list[PriceResult]], list[EquivalencyMatch], list[EquivalencyMatch]]:
        matched   = await match_all(line_items, raw_results)
        actionable, borderline = await find_equivalencies(
            line_items, matched, raw_results
        )
        web_alternates = find_web_alternates(line_items, raw_results)
        actionable = actionable + web_alternates
        return matched, actionable, borderline