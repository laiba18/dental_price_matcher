"""
models.py — Pydantic data models for the full Stage 1 + 2 pipeline.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


# ─── Parsed product description (from AI) ────────────────────────────────────

class ParsedDescription(BaseModel):
    brand: Optional[str] = None
    product_name: Optional[str] = None
    form: Optional[str] = None           # compule, syringe, powder, bur, file…
    pack_qty: Optional[float] = None     # numeric qty in pack e.g. 20
    pack_unit: Optional[str] = None      # box, bag, pack, roll…
    shade: Optional[str] = None
    viscosity: Optional[str] = None
    size_info: Optional[str] = None      # "25mm", "59ml", "1.2mL"…
    manufacturer_part_number: Optional[str] = None   # MPN where determinable
    parse_confidence: float = 0.0


# ─── Single line item from the Henry Schein order ─────────────────────────────

class LineItem(BaseModel):
    line_number: int
    schein_sku: str
    description_raw: str
    description_parsed: Optional[ParsedDescription] = None
    qty: int
    uom: str
    unit_price: float
    ext_price: float


# ─── Full extracted order ─────────────────────────────────────────────────────

class OrderExtraction(BaseModel):
    order_ref: Optional[str] = None
    order_date: Optional[str] = None
    patient_name: Optional[str] = None
    total_price: Optional[float] = None
    line_items: list[LineItem]
    raw_text: str


# ─── Price result from one supplier site ─────────────────────────────────────

class PriceResult(BaseModel):
    line_item_id: int                    # index into line_items list
    supplier: str
    price: Optional[float] = None
    url: Optional[str] = None
    pack_qty: Optional[float] = None
    pack_unit: Optional[str] = None
    pack_condition_note: Optional[str] = None   # e.g. "6-pack price"
    match_type: Optional[Literal["exact", "pack_mismatch", "approximate"]] = None
    match_confidence: float = 0.0
    matched_brand: bool = False
    matched_product_name: bool = False
    matched_form: bool = False
    matched_pack_qty: bool = False
    match_reasoning: Optional[str] = None
    login_required: bool = False
    blocked: bool = False
    no_public_price: bool = False
    raw_text: Optional[str] = None
    source: str = "supplier_site"        # "supplier_site" | "web_sweep"


# ─── Market sweep result (broad web search) ───────────────────────────────────

class WebSweepResult(BaseModel):
    line_item_id: int
    query_used: str
    price: Optional[float] = None
    url: Optional[str] = None
    site_name: Optional[str] = None
    raw_snippet: Optional[str] = None


# ─── Equivalency match (Stage 2) ─────────────────────────────────────────────

class EquivalencyMatch(BaseModel):
    line_item_id: int
    schein_sku: str
    schein_price: float
    equiv_product: str
    equiv_brand: Optional[str] = None
    equiv_supplier: Optional[str] = None
    equiv_price: Optional[float] = None
    equiv_url: Optional[str] = None
    confidence: Literal["exact", "close", "possible"]
    basis: str
    estimated_savings: Optional[float] = None


# ─── Final run summary ────────────────────────────────────────────────────────

class RunResult(BaseModel):
    order_id: int
    order_ref: Optional[str]
    order_date: Optional[str]
    patient_name: Optional[str]
    line_item_count: int
    matched_count: int
    equiv_count: int
    total_potential_savings: float
    output_price_match: str
    output_alternate_purchase: str
    output_evidence: str
    created_at: datetime = Field(default_factory=datetime.now)
