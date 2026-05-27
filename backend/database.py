"""
database.py — SQLite schema covering all 4 stages.
Stages 3 & 4 tables are defined but left empty at launch.
"""

import aiosqlite
import asyncio
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "dental.db"

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ── STAGE 1 + 2 ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    filename      TEXT    NOT NULL,
    file_hash     TEXT    NOT NULL UNIQUE,
    order_ref     TEXT,
    order_date    TEXT,
    patient_name  TEXT,
    total_price   REAL,
    item_count    INTEGER,
    status        TEXT    NOT NULL DEFAULT 'pending',
    output_price_match      TEXT,
    output_alternate        TEXT,
    output_evidence         TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS line_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id            INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    line_number         INTEGER NOT NULL,
    schein_sku          TEXT    NOT NULL,
    description_raw     TEXT    NOT NULL,
    description_parsed  TEXT,
    manufacturer_pn     TEXT,
    parse_confidence    REAL,
    qty                 INTEGER,
    uom                 TEXT,
    unit_price          REAL,
    ext_price           REAL
);

CREATE TABLE IF NOT EXISTS price_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    line_item_id        INTEGER NOT NULL REFERENCES line_items(id) ON DELETE CASCADE,
    supplier            TEXT    NOT NULL,
    price               REAL,
    url                 TEXT,
    pack_qty            REAL,
    pack_unit           TEXT,
    pack_condition_note TEXT,
    match_type          TEXT,
    match_confidence    REAL,
    matched_brand       INTEGER DEFAULT 0,
    matched_product     INTEGER DEFAULT 0,
    matched_form        INTEGER DEFAULT 0,
    matched_pack        INTEGER DEFAULT 0,
    match_reasoning     TEXT,
    login_required      INTEGER DEFAULT 0,
    blocked             INTEGER DEFAULT 0,
    no_public_price     INTEGER DEFAULT 0,
    raw_text            TEXT,
    source              TEXT    DEFAULT 'supplier_site',
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS equivalency_matches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    line_item_id        INTEGER NOT NULL REFERENCES line_items(id) ON DELETE CASCADE,
    schein_sku          TEXT,
    schein_price        REAL,
    equiv_product       TEXT    NOT NULL,
    equiv_brand         TEXT,
    equiv_supplier      TEXT,
    equiv_price         REAL,
    equiv_url           TEXT,
    confidence          TEXT,
    basis               TEXT,
    estimated_savings   REAL,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── STAGE 3 (stubbed — empty at launch) ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS order_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    schein_sku  TEXT    NOT NULL,
    order_date  TEXT    NOT NULL,
    qty         REAL,
    unit_price  REAL,
    order_id    INTEGER REFERENCES orders(id)
);

-- ── STAGE 4 (stubbed — empty at launch) ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS inventory_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    schein_sku      TEXT    NOT NULL UNIQUE,
    product_name    TEXT,
    par_level       REAL,
    current_stock   REAL,
    uom             TEXT
);

CREATE TABLE IF NOT EXISTS usage_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    schein_sku      TEXT    NOT NULL,
    week_ending     TEXT    NOT NULL,
    qty_used        REAL,
    avg_weekly_use  REAL
);

CREATE TABLE IF NOT EXISTS reorder_projections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    schein_sku      TEXT    NOT NULL,
    projected_date  TEXT,
    projected_qty   REAL,
    confidence      REAL
);
"""


async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


if __name__ == "__main__":
    asyncio.run(init_db())
    print(f"Database ready at {DB_PATH}")
