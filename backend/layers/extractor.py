"""
layers/extractor.py — PDF extraction layer.

Verified against 4 real Henry Schein order PDFs.
The PDF renders each table cell on its own line, giving a clean
6-line repeating pattern: qty → SKU → description → UOM → unit_price → ext_price.
State-machine parser — zero false positives on real data.
"""

import re
import hashlib
import fitz   # PyMuPDF
from pathlib import Path
from backend.models import LineItem, OrderExtraction


# ── Cell-type matchers ────────────────────────────────────────────────────────
_QTY_RE   = re.compile(r"^\d{1,4}$")
_SKU_RE   = re.compile(r"^\d{5,8}$")
_UOM_RE   = re.compile(r"^[A-Z]{2,4}$")
_PRICE_RE = re.compile(r"^\$[\d,]+\.\d{2}$")

# Lines that terminate the current table section (footer / address / page break)
_STOP_RE = re.compile(
    r"^(Total:|Total Price|Actual price|315 |PO Box|\d{2}/\d{2}/\d{4}|www\.henry)",
    re.I,
)


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_price(s: str) -> float:
    return float(s.replace("$", "").replace(",", ""))


def extract(file_path: Path) -> OrderExtraction:
    """
    Open the PDF and extract every order line item.
    Works across multiple pages — the table header triggers the parser
    each time it appears so continuation pages are handled automatically.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    doc = fitz.open(str(file_path))
    if doc.page_count == 0:
        raise ValueError("PDF has no pages")

    full_text = ""
    for page in doc:
        full_text += page.get_text("text")
    doc.close()

    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    # ── Header metadata ───────────────────────────────────────────────────────
    order_ref    = None
    order_date   = None
    patient_name = None
    total_price  = None

    for i, l in enumerate(lines):
        if l == "Reference" and i + 1 < len(lines):
            order_ref = lines[i + 1]
        if l == "Ship to" and i + 1 < len(lines):
            patient_name = lines[i + 1]
        dm = re.search(r"(\d{2}/\d{2}/\d{4})", l)
        if dm and not order_date:
            order_date = dm.group(1)
        tm = re.match(r"Total(?:\s+Price)?:\s*\$([\d,]+\.\d{2})", l)
        if tm and not total_price:
            total_price = float(tm.group(1).replace(",", ""))
        # "Total Price" on its own line, value on next
        if l == "Total Price" and i + 1 < len(lines):
            pm = re.match(r"\$([\d,]+\.\d{2})", lines[i + 1])
            if pm and not total_price:
                total_price = float(pm.group(1).replace(",", ""))

    # ── Line-item state machine ───────────────────────────────────────────────
    items: list[LineItem] = []
    item_count = 0
    in_table = False
    i = 0

    while i < len(lines):
        l = lines[i]

        # Table header: "Qty" immediately followed by "Product"
        if l == "Qty" and i + 1 < len(lines) and lines[i + 1] == "Product":
            in_table = True
            i += 6  # skip: Qty Product Description UOM Unit Price Extended Price
            continue

        if not in_table:
            i += 1
            continue

        # Footer / address lines reset table state;
        # the next page's header will re-enable it
        if _STOP_RE.match(l):
            in_table = False
            i += 1
            continue

        # Try to consume a 6-line block
        if (i + 5 < len(lines)
                and _QTY_RE.match(l)
                and _SKU_RE.match(lines[i + 1])
                and _UOM_RE.match(lines[i + 3])
                and _PRICE_RE.match(lines[i + 4])
                and _PRICE_RE.match(lines[i + 5])):

            item_count += 1
            items.append(LineItem(
                line_number=item_count,
                schein_sku=lines[i + 1],
                description_raw=lines[i + 2],
                qty=int(l),
                uom=lines[i + 3],
                unit_price=_parse_price(lines[i + 4]),
                ext_price=_parse_price(lines[i + 5]),
            ))
            i += 6
        else:
            i += 1

    return OrderExtraction(
        order_ref=order_ref,
        order_date=order_date,
        patient_name=patient_name,
        total_price=total_price,
        line_items=items,
        raw_text=full_text,
    )
