"""
layers/intelligence.py — Firecrawl-powered web search + price extraction.

.env keys needed:
  FIRECRAWL_API_KEY  — get free at https://www.firecrawl.dev (500 pages/month)
  GROQ_API_KEY       — for description parsing (existing)

Two-step pipeline per item:
  Step 1 — Firecrawl search()  — finds the top 5 dental supplier pages
            → returns title, URL, and page markdown in ONE call
            → blocked domains filtered out before any scraping
            → 3 best matches for File 1 (Price Match)

  Step 2 — Firecrawl scrape_url()  — for each search result URL:
            → fetches the full product page (renders JS, handles anti-bot)
            → extracts exact price from full page content
            → much more accurate than extracting from search snippet

  Step 3 — Fallback search  — parsed short query for File 2 (Alternate Purchase)
            → same domain filter + product-relevance filter

Credit usage (free tier = 500 pages/month):
  - search() = 1 credit per search (returns up to 5 results + content)
  - scrape_url() = 1 credit per page scraped
  Per 12-item order: ~12 searches (step 1) + up to 36 scrapes (step 2) = ~48 credits
  Free tier: 500 / 48 = ~10 full orders/month free

Firecrawl vs Brave+Jina:
  - Brave: returns search snippets only (price often not in snippet)
  - Jina: fetches page but rate limits and token costs ate credits fast
  - Firecrawl: renders JS-heavy pages (dynamic prices load correctly),
               handles anti-bot, returns clean markdown, 500 free/month
"""

import asyncio
import json
import os
import re
import unicodedata
from urllib.parse import urlparse

from dotenv import load_dotenv
from firecrawl import AsyncV1FirecrawlApp
from groq import AsyncGroq, RateLimitError

from backend.models import LineItem, ParsedDescription, PriceResult, WebSweepResult
from backend.layers.matcher import (
    _score_exact_input_match,
    _score_equiv_alternate_match,
    _extract_qty_from_title,
    format_match_reasoning,
    load_equivalency_table,
)

load_dotenv()

_groq    = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
_fc_key  = os.getenv("FIRECRAWL_API_KEY", "")

_SEARCH_DELAY   = 1.0   # seconds between Firecrawl search calls
_SCRAPE_DELAY   = 0.5   # seconds between scrape calls (concurrent within item)
_ITEM_DELAY     = 1.0   # seconds between items
_PARSE_DELAY    = 3.5   # seconds between Groq calls
_EXACT_TARGET   = 3     # results to show in File 1
_SCRAPE_TIMEOUT = 20000 # ms — Firecrawl timeout per page

PRICE_DOLLAR_RE = re.compile(r"\$\s*([\d,]+\.\d{2})")
PRICE_BARE_RE   = re.compile(
    r"(?<![\d.])(?:(?:USD|CAD)\s*)?([\d]{1,4}(?:,\d{3})*\.\d{2})(?!\d)", re.I,
)


# ─── Domain blocklist ─────────────────────────────────────────────────────────

_BLOCKED_DOMAINS = {
    "henryschein.com", "henryschein.ca", "henryscheinbrand.com",
    "henryschein.co.uk", "henryschein.com.au", "henryscheindental.com",
    "3m.com", "multimedia.3m.com",
    "amazon.com", "amazon.ca", "amazon.co.uk",
    "ebay.com", "ebay.ca", "ebay.co.uk",
    "walmart.com", "walmart.ca",
    "drugs.com", "drugstore.com",
    "dailymed.nlm.nih.gov", "nlm.nih.gov",
    "rxlist.com", "medicinenet.com",
    "webmd.com", "healthline.com",
    "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov",
    "sciencedirect.com", "springer.com",
    "wiley.com", "tandfonline.com",
    "researchgate.net",
    "nxtbook.com", "issuu.com", "scribd.com",
    "dentalproductshopper.com",
    "luggagebase.com", "livinggracecatalog.com",
    "sourceonedental.com", "amdnext.com", "integratedmc.com",
    "youtube.com", "facebook.com", "instagram.com",
    "pinterest.com", "reddit.com",
}

_BLOCKED_PATH_RE = re.compile(
    r"(/MSDS/|/msds/|\.pdf$|/media/|/mws/media/|"
    r"/pro/|/drug-info/|/article/|/research/|/study/|"
    r"/blog/|/news/|/press/|/whitepaper/)",
    re.I,
)

_JUNK_TITLE_RE = re.compile(
    r"^(house brand|add to cart|shop now|best seller|free shipping|"
    r"\d+\s*results?|effectiveness of|study of|"
    r"\.pdf$|msds|safety data sheet|"
    r"journal of|international journal|"
    r"amazon\.com|ebay\.com)",
    re.I,
)

_DENTAL_RELEVANCE_RE = re.compile(
    r"\b(dental|tooth|teeth|oral|anesthetic|anesthesia|"
    r"prophy|composite|fluoride|sealant|glove|syringe|"
    r"mixing tip|impression|barrier|evacuation|floss|"
    r"toothpaste|creme|cream|paste|gel|rinse|"
    r"supply|supplies|equipment|product|item|pack|box|"
    r"mg|oz|ml|mm|cc|liter)\b",
    re.I,
)

_RESEARCH_TITLE_RE = re.compile(
    r"^(effectiveness|efficacy|clinical|comparison|"
    r"randomized|systematic review|meta-analysis|"
    r"in vitro|in vivo|study of|evaluation of|"
    r"effect of|assessment of)",
    re.I,
)

_DOMAIN_SUPPLIERS: dict[str, str] = {
    "net32.com":               "Net32",
    "crazydentalprices.com":   "Crazy Dental Prices",
    "ansondental.com":         "Anson Dental",
    "mvpdentalsupply.com":     "MVP Dental Supply",
    "mvpdental.com":           "MVP Dental",
    "pricenex.com":            "Pricenex",
    "tdsc.com":                "TDSC",
    "safcodental.com":         "Safco Dental Supply",
    "dentalcity.com":          "Dental City",
    "myddssupply.com":         "My DDS Supply",
    "optimusdentalsupply.com": "Optimus Dental Supply",
    "medexsupply.com":         "Medex Supply",
    "pattersondental.com":     "Patterson Dental",
    "darbydental.com":         "Darby Dental",
    "benco.com":               "Benco Dental",
    "ultradent.com":           "Ultradent",
    "scottsdental.com":        "Scott's Dental",
    "newarkdentalpemco.com":   "Newark Dental",
    "thedentalmarket.net":     "The Dental Market",
    "atlantadental.com":       "Atlanta Dental Supply",
    "medicalproductssupply.com": "Medical Products Supply",
    "nimmed.com":              "NIM Medical",
    "amtouch.com":             "Amtouch Dental",
    "camsupply.com":           "CAM Supply",
    "sabradent.com":           "Sabradent",
    "ddsdentalsupplies.com":   "DDS Dental Supplies",
    "supplyclinic.com":        "Supply Clinic",
    "shop.benco.com":          "Benco Dental",
    "americangoods.nyc":       "Americangoods",
}


# ─── Filtering helpers ────────────────────────────────────────────────────────

def _is_blocked(url: str, title: str) -> bool:
    parsed = urlparse(url)
    host   = parsed.netloc.lower().replace("www.", "")
    if host in _BLOCKED_DOMAINS:
        return True
    for blocked in _BLOCKED_DOMAINS:
        if host.endswith("." + blocked) or host == blocked:
            return True
    if _BLOCKED_PATH_RE.search(parsed.path):
        return True
    if _JUNK_TITLE_RE.search(title.strip()):
        return True
    return False


def _is_relevant_title(title: str, query: str) -> bool:
    if _RESEARCH_TITLE_RE.match(title.strip()):
        return False
    query_words = set(
        w for w in re.sub(r"[^a-z0-9\s]", "", query.lower()).split()
        if len(w) > 2
    )
    title_lower = title.lower()
    return (
        any(w in title_lower for w in query_words)
        and bool(_DENTAL_RELEVANCE_RE.search(title))
    )


def _normalize_title(text: str) -> str:
    text = _fix_unicode(text.lower())
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _title_matches_exact(title: str, description: str, parsed: dict | None = None) -> bool:
    t_norm = _normalize_title(title)
    if not t_norm:
        return False
    desc_words = [
        w for w in _normalize_title(description).split()
        if len(w) > 2 and w not in _EXACT_STOPWORDS
    ]
    if not desc_words:
        return False
    brand = (parsed or {}).get("brand") or ""
    if brand:
        brand_flat = re.sub(r"[^a-z0-9]", "", brand.lower())
        title_flat = re.sub(r"[^a-z0-9]", "", t_norm)
        if brand_flat and brand_flat not in title_flat:
            alt = brand_flat.replace("-", "")
            if alt not in title_flat:
                return False
    t_words = set(t_norm.split())
    hits = sum(1 for w in desc_words if w in t_words or w in t_norm)
    need = min(len(desc_words), max(3, int(len(desc_words) * 0.55)))
    return hits >= need


_UNAVAILABLE_PAGE_RE = re.compile(
    r"(?:out\s+of\s+stock|currently\s+unavailable|not\s+currently\s+available|"
    r"product\s+unavailable|temporarily\s+unavailable|discontinued|"
    r"too\s+little\s+or\s+no\s+stock|no\s+stock\s+available|sold\s+out)",
    re.I,
)

_ERROR_PAGE_RE = re.compile(
    r"(?:page\s+not\s+found|404\s+error|this\s+page\s+(?:couldn'?t|could\s+not)\s+be\s+found|"
    r"product\s+(?:you\s+are\s+looking\s+for\s+)?(?:was\s+)?not\s+found)",
    re.I,
)

_NON_DENTAL_PRODUCT_RE = re.compile(
    r"\b(incontinence|underwear|diaper|tena\b|adult\s+brief|grocer|grocery|fresh\s*market)\b",
    re.I,
)

_TRAVEL_LUGGAGE_RE = re.compile(
    r"\b(samsonite|spinner|softside|luggage|suitcase|carry[- ]?on|"
    r"checked\s+bag|travel\s+bag|carry\s+bag|tumi\b|away\s+luggage)\b",
    re.I,
)

_DENTAL_SUPPLY_LINE_RE = re.compile(
    r"\b(dental|prophy|denture|syringe|sealant|mask|nasal|evacuation|"
    r"anesthetic|composite|cement|bur\b|burs\b|handpiece|orthodont|"
    r"implant|fluoride|glove|bib|nitrous|porter|plasdent|luxatemp|"
    r"mixing\s+tip|barrier\s+film|prophy\s+angle)\b",
    re.I,
)

_PRICE_SECTION_CUT_RE = re.compile(
    r"(?i)(?:^|\n)#+\s*(?:Related\s+Products|Related\s+Items|You\s+May\s+Also\s+Like|"
    r"Customers\s+Also\s+(?:Bought|Viewed)|Similar\s+Items|Recently\s+Viewed)\b"
)


def _page_is_unavailable(content: str, title: str = "") -> bool:
    return bool(_UNAVAILABLE_PAGE_RE.search(f"{title}\n{content}"))


def _page_is_error(content: str, title: str = "") -> bool:
    sample = f"{title}\n{content}"
    if len(content) < 5000 and _ERROR_PAGE_RE.search(sample):
        return True
    return False


def _is_non_dental_product_hit(
    title: str,
    url: str,
    content: str = "",
    schein_description: str = "",
) -> bool:
    combined = f"{title} {url} {content[:3000]}".lower()
    if _NON_DENTAL_PRODUCT_RE.search(combined):
        return True
    if re.search(r"(fresh[- ]?market|/products/tena-|incontinence-underwear)", combined):
        return True
    if _TRAVEL_LUGGAGE_RE.search(combined):
        if _DENTAL_SUPPLY_LINE_RE.search(schein_description):
            return True
        if not _DENTAL_SUPPLY_LINE_RE.search(combined):
            return True
    # Generic brand name collision (Silhouette luggage vs Porter nasal mask)
    if schein_description and _DENTAL_SUPPLY_LINE_RE.search(schein_description):
        if _TRAVEL_LUGGAGE_RE.search(combined) and not re.search(
            r"\b(dental|nasal|mask|porter|nitrous|breathing)\b", combined, re.I
        ):
            return True
    return False


def _is_suspicious_price(price: float, schein_price: float) -> bool:
    if price < 0.50:
        return True
    if schein_price >= 5 and price < 1.0:
        return True
    if schein_price > 0 and price < schein_price * 0.10 and price < 5:
        return True
    if schein_price >= 20 and price < schein_price * 0.12:
        return True
    return False


def _main_product_content(content: str) -> str:
    """Drop related-product sections that inject lower prices from other SKUs."""
    if not content:
        return ""
    m = _PRICE_SECTION_CUT_RE.search(content)
    if m:
        return content[:m.start()]
    return content


def _supplier_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().replace("www.", "")
    for domain, name in _DOMAIN_SUPPLIERS.items():
        if domain in host:
            return name
    base = host.split(".")[0]
    return base.replace("-", " ").replace("_", " ").title() or host


# ─── Unicode / local parse ────────────────────────────────────────────────────

def _fix_unicode(text: str) -> str:
    return unicodedata.normalize("NFKD", text)


_PACK_QTY_RE = re.compile(r"(\d+)\s*/\s*(Bx|Pk|Bg|Jr|Bt|Rl|Ea|CS|KT)\b", re.I)
_SIZE_STRIP  = re.compile(r"\d+(?:\.\d+)?\s*(?:mm|ml|mL|cc|oz|Liter|Meter)", re.I)
_PACK_STRIP  = re.compile(r"\d+\s*/\s*(?:Bx|Pk|Bg|Jr|Bt|Rl|Ea|CS|KT)\b", re.I)
_EXACT_STRIP = re.compile(
    r"\d+\s*/\s*(?:Bx|Pk|Bg|Jr|Bt|Rl|Ea|CS|KT)\b"
    r"|\d+(?:\.\d+)?\s*(?:mm|ml|mL|cc|oz|Liter|Meter)"
    r"|\b(Pkg|Non-Ster|Unfl|Unflavored|Trtm|No\s+Flavor|SC)\b",
    re.I,
)
_EXACT_STOPWORDS = {"ea", "pkg", "non", "ster", "unfl", "trtm", "flavor", "sc"}

_KNOWN_BRANDS = [
    "3M", "Oral-B", "Dentsply", "Kerr", "Ivoclar", "Sultan", "GC America",
    "Mani", "Septodont", "Ultradent", "Shofu", "VOCO", "Bisco", "Brasseler",
    "Komet", "Coltene", "Luxatemp", "Acclean", "Silhouette", "Purevac",
    "Clinpro", "Maxima", "Luer", "NTI", "Parkell", "SDI", "Hu-Friedy",
    "Premier", "Pulpdent", "Heraeus", "Kulzer", "Darby", "Defend", "Benzo-Jel",
]

_STOPWORDS = {
    "ea", "refill", "refl", "pkg", "non", "ster", "assorted", "cc", "st",
    "hp", "plus", "fine", "soft", "short", "medium", "and", "the", "for",
    "with", "per", "dental", "supply", "size", "type", "kit", "set",
    "pack", "box", "bag", "each", "unfl", "unflavored", "flavor",
}


def _parse_local(description: str) -> dict:
    description = _fix_unicode(description)
    brand = None
    for b in _KNOWN_BRANDS:
        if re.search(r"\b" + re.escape(b) + r"\b", description, re.I):
            brand = b
            break

    pack_qty, pack_unit = None, None
    pm = _PACK_QTY_RE.search(description)
    if pm:
        pack_qty  = int(pm.group(1))
        pack_unit = pm.group(2).lower()

    pname = description
    pname = _PACK_STRIP.sub("", pname)
    pname = _SIZE_STRIP.sub("", pname)
    if brand:
        pname = re.sub(r"\b" + re.escape(brand) + r"\b", "", pname, flags=re.I)
    pname = re.sub(r"\b(Ea|Refill|Refl|Pkg|Non-Ster|Assorted|ST|HP|SC|CC|FK|Unfl)\b",
                   "", pname, flags=re.I)
    pname = re.sub(r'["\'/\\,]', " ", pname)
    pname = re.sub(r"\s+", " ", pname).strip().strip("-").strip()

    raw   = _PACK_STRIP.sub("", description)
    raw   = _SIZE_STRIP.sub("", raw)
    raw   = re.sub(r'["\'/\\,]', " ", raw)
    words = [w for w in raw.split() if len(w) > 2 and w.lower() not in _STOPWORDS]

    return {
        "brand":            brand,
        "product_name":     pname or description,
        "pack_qty":         pack_qty,
        "pack_unit":        pack_unit,
        "search_query":     " ".join(words[:5]),
        "parse_confidence": 0.65,
    }


def _make_raw_input_query(description: str) -> str:
    """Full PDF line text for exact search — keeps pack/size (e.g. 1oz/Jr, 100/Bx)."""
    desc = _fix_unicode(description.strip())
    desc = re.sub(r'["\'/\\,]', " ", desc)
    return re.sub(r"\s+", " ", desc).strip()


def _make_exact_query(description: str, parsed: dict) -> str:
    """Clean search query: strips pack/size/junk, keeps brand + product name."""
    desc  = _fix_unicode(description)
    desc  = _EXACT_STRIP.sub(" ", desc)
    desc  = re.sub(r'["\'/\\,]', " ", desc)
    desc  = re.sub(r"\s+", " ", desc).strip()
    words = [w for w in desc.split()
             if len(w) > 2 and w.lower() not in _EXACT_STOPWORDS]

    brand   = (parsed.get("brand") or "").strip()
    product = (parsed.get("product_name") or "").strip()
    if brand and product and len(brand) > 2:
        pwords = [
            w for w in product.split()
            if len(w) > 2
            and w.lower() not in _EXACT_STOPWORDS
            and w.lower() != brand.lower()
        ][:4]
        parsed_q = f"{brand} {' '.join(pwords)}".strip()
        if len(parsed_q.split()) >= len(words[:6]):
            return parsed_q

    return " ".join(words[:6])


def _fallback_queries(parsed: dict, raw_description: str) -> list[str]:
    """Parsed short queries for File 2 alternate search (no full raw input)."""
    queries: list[str] = []
    sq = (parsed.get("search_query") or "").strip()
    if sq:
        queries.append(sq)

    brand   = parsed.get("brand")
    product = (parsed.get("product_name") or "").strip()
    if brand and product:
        words = [w for w in product.split() if len(w) > 2][:3]
        q = f"{brand} {' '.join(words)}".strip()
        if q and q.lower() not in {x.lower() for x in queries}:
            queries.append(q)

    if sq:
        q2 = sq + " dental supply"
        if q2.lower() not in {x.lower() for x in queries}:
            queries.append(q2)

    return queries[:3]


# ─── Pack / qty validation ────────────────────────────────────────────────────

def _extract_qty_from_text(text: str) -> int | None:
    """Delegate to matcher pack-qty parser (comma numbers, sheets/roll, etc.)."""
    return _extract_qty_from_title(text)


def _product_match_text(title: str, content: str) -> str:
    """Title plus pack/product lines from page content for accurate matching."""
    parts: list[str] = []
    if title.strip():
        parts.append(title.strip())
    if content:
        for pat in (
            r"(?i)(?:Item\s+includes|Includes|Contains):\s*([^\n]{5,120})",
            r"(?i)([\d,]+\s+(?:\d+\s*(?:\"|in|inch)?\s*(?:x|×)\s*\d+\s*(?:\"|in|inch)?\s*)?"
            r"sheets?\s*per\s*(?:roll|box|pack|bag)[^\n]*)",
            r"(?i)Packaging:\s*([^\n]{3,80})",
            r"(?i)(?:Count|Pack\s*Size)[^\n|]*\|\s*(\d+\s*per\s*(?:box|pack|bag|roll)[^\n]*)",
            r"(?i)Product\s+Name:\s*([^\n]+)",
            r"(?i)([\d,]+\s*/\s*(?:bx|pk|box|pack|bag|roll|rl)[^\n,.]{0,30})",
            r"(?i)Our\s+Price:\s*\$[\d,]+\.\d{2}[^\n]*([\d,]+\s*/\s*(?:bx|pk|box|roll)[^\n]*)?",
        ):
            for m in re.finditer(pat, content[:10000]):
                chunk = (m.group(1) if m.lastindex else m.group(0)).strip()
                if chunk and chunk not in parts:
                    parts.append(chunk)
    return " ".join(parts)[:400]


def _is_variable_price_page(content: str) -> bool:
    return bool(re.search(
        r"\$[\d,]+\.\d{2}\s*[–—\-]\s*\$[\d,]+\.\d{2}",
        content or "",
    ))


def _pack_search_queries(parsed: dict) -> list[str]:
    """Queries that keep pack count — critical for 500/bx vs 100/bx products."""
    queries: list[str] = []
    pack_qty = parsed.get("pack_qty")
    brand    = (parsed.get("brand") or "").strip()
    product  = (parsed.get("product_name") or "").strip()
    if not pack_qty:
        return queries

    if brand and product:
        q = re.sub(r"\s+", " ", f"{brand} {product} {pack_qty} bx").strip()
        if q:
            queries.append(q)

    pwords = [
        w for w in product.split()
        if len(w) > 2 and w.lower() not in _STOPWORDS
    ][:4]
    if pwords:
        q2 = re.sub(r"\s+", " ", f"{' '.join(pwords)} {pack_qty} bx").strip()
        if q2.lower() not in {x.lower() for x in queries}:
            queries.append(q2)

    return queries[:2]


def _file1_search_complete(pool: list[PriceResult], item: LineItem) -> bool:
    """Enough results only when pack-sized items have at least one pack-confirmed hit."""
    picked = _pick_top_three(pool)
    if len(picked) < _EXACT_TARGET:
        return False
    pd = item.description_parsed
    if pd and pd.pack_qty:
        return any(r.matched_pack_qty for r in picked)
    return True


def _check_pack_mismatch(
    schein_pack_qty: int | None,
    result_title: str,
    result_price: float,
    schein_price: float,
    result_content: str = "",
) -> tuple[bool, str]:
    if schein_price <= 0:
        return False, ""
    ratio = result_price / schein_price
    if ratio < 0.15:
        return True, (
            f"⚠ Pack mismatch likely: ${result_price:.2f} is only {ratio:.0%} of "
            f"Schein ${schein_price:.2f} — check if single-unit vs "
            f"{schein_pack_qty or '?'}-pack"
        )
    if schein_pack_qty:
        result_qty = _extract_qty_from_text(f"{result_title}\n{result_content[:5000]}")
        if result_qty and result_qty != schein_pack_qty:
            if result_qty < schein_pack_qty / 2 or result_qty > schein_pack_qty * 2:
                return True, (
                    f"⚠ Pack size: Schein={schein_pack_qty}, found={result_qty} — "
                    f"adjust per-unit comparison before negotiating"
                )
    return False, ""


def _page_pack_conflicts(schein_pack_qty: int | None, title: str, content: str) -> bool:
    """True when page states a pack count that clearly differs from Schein."""
    if not schein_pack_qty:
        return False
    page_qty = _extract_qty_from_text(f"{title}\n{content[:8000]}")
    if page_qty is None:
        return False
    return abs(page_qty - schein_pack_qty) > max(1, schein_pack_qty * 0.15)


# ─── Price extraction from page text ─────────────────────────────────────────

def _extract_excluded_price_amounts(content: str) -> set[float]:
    excluded: set[float] = set()
    patterns = [
        r"(?:You\s+save|\(You\s+save)\s+\$?\s*([\d,]+\.\d{2})",
        r"(?:MSRP|Was|RRP|List\s+Price|Regular\s+Price|Compare\s+at)[:\s]*\$?\s*([\d,]+\.\d{2})",
        r"Save\s+\$?\s*([\d,]+\.\d{2})\s*(?:\)|%|\*\*)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, content, re.I):
            try:
                excluded.add(float(m.group(1).replace(",", "")))
            except ValueError:
                pass
    return excluded


def _extract_structured_prices(content: str) -> list[tuple[float, int]]:
    """Return (price, priority) — lower priority = preferred current selling price."""
    if not content:
        return []
    excluded = _extract_excluded_price_amounts(content)
    found: list[tuple[float, int]] = []

    def _add(val: str, priority: int) -> None:
        try:
            p = float(str(val).replace(",", ""))
            if p in excluded or not (0.50 < p < 5000):
                return
            found.append((p, priority))
        except ValueError:
            pass

    # DDS BigCommerce — first "Now:" is the main product price
    m_now = re.search(r"Now:\s*\$?\s*([\d,]+\.\d{2})", content, re.I)
    if m_now:
        _add(m_now.group(1), 0)

    # TDSC markdown: YOUR PRICE\\ on one line, $6.50 on the next
    m_yp = re.search(
        r"YOUR\s+PRICE\\?\s*\n\s*\$([\d,]+\.\d{2})",
        content,
        re.I,
    )
    if m_yp:
        _add(m_yp.group(1), 0)

    m_yp2 = re.search(
        r"YOUR\s+PRICE[^\d$]{0,40}\$([\d,]+\.\d{2})",
        content,
        re.I | re.S,
    )
    if m_yp2:
        _add(m_yp2.group(1), 0)

    m_vip = re.search(r"VIP\s+PRICE\\?\s*\n\s*\$([\d,]+\.\d{2})", content, re.I)
    if m_vip:
        _add(m_vip.group(1), 2)

    # BigCommerce / Pricenex — main product price before cart controls
    m_bc = re.search(
        r"\$\s*([\d,]+\.\d{2})\s*\n\s*Current\s+Stock",
        content,
        re.I,
    )
    if m_bc:
        _add(m_bc.group(1), 0)

    m_bc2 = re.search(
        r"(?i)^#\s+[^\n]+\n(?:.*\n){0,20}?\$\s*([\d,]+\.\d{2})\s*$",
        content,
        re.M,
    )
    if m_bc2:
        _add(m_bc2.group(1), 0)

    # Meta / schema prices
    m_meta = re.search(r'product:price:amount["\']\s*content=["\']([\d.]+)["\']', content, re.I)
    if m_meta:
        _add(m_meta.group(1), 1)

    m_ld = re.search(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
        content,
        re.I,
    )
    if m_ld:
        try:
            data = json.loads(m_ld.group(1))
            offers = data.get("offers") or {}
            if isinstance(offers, dict):
                for key in ("price", "lowPrice"):
                    if offers.get(key):
                        _add(str(offers[key]), 2)
        except (json.JSONDecodeError, ValueError):
            pass

    return found


def _pick_structured_price(candidates: list[tuple[float, int]]) -> float | None:
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[1], x[0]))
    best_pri = candidates[0][1]
    for price, pri in candidates:
        if pri == best_pri:
            return price
    return None


def _extract_price(title: str, content: str, query: str) -> float | None:
    """Extract current selling price — prefers Now:/YOUR PRICE over savings amounts."""
    main = _main_product_content(content)
    structured = _pick_structured_price(_extract_structured_prices(f"{title}\n{main}"))
    if structured is not None:
        return structured

    query_words = {
        w for w in re.sub(r"[^a-z0-9\s]", "", query.lower()).split()
        if len(w) > 2
    }
    text  = f"{title}\n{main[:12000]}"
    lines = text.split("\n")
    best  = None

    for i, line in enumerate(lines):
        if re.search(
            r"(?:you\s+save|msrp|was:|compare\s+at|save\s+\$|related\s+products|quick\s+view)",
            line,
            re.I,
        ):
            continue
        prices: list[float] = []
        for m in PRICE_DOLLAR_RE.finditer(line):
            p = float(m.group(1).replace(",", ""))
            if 0.50 < p < 5000:
                prices.append(p)
        if not prices and re.search(r"[a-zA-Z]", line):
            for m in PRICE_BARE_RE.finditer(line):
                p = float(m.group(1).replace(",", ""))
                if 0.50 < p < 5000:
                    prices.append(p)
        if not prices:
            continue
        ctx   = " ".join(lines[max(0, i-5): min(len(lines), i+6)]).lower()
        score = sum(1 for w in query_words if w in ctx)
        # First price on the best-scoring earliest line — not cheapest site-wide
        price = prices[0]
        if (
            best is None
            or score > best["score"]
            or (score == best["score"] and i < best["line_idx"])
        ):
            best = {"price": price, "score": score, "line_idx": i}

    return best["price"] if best else None


# ─── Groq description parser ──────────────────────────────────────────────────

PARSE_SYSTEM = """You parse Henry Schein dental supply descriptions into structured JSON.
Return ONLY valid JSON.

Schema:
{
  "brand": string or null,
  "product_name": string or null,
  "form": string or null,
  "pack_qty": number or null,
  "pack_unit": string or null,
  "shade": string or null,
  "viscosity": string or null,
  "size_info": string or null,
  "manufacturer_part_number": string or null,
  "search_query": string,
  "parse_confidence": number 0.0-1.0
}
search_query = best 3-5 word query (brand + product name, no pack size).
Abbreviations: /Bx=box /Pk=pack /Bg=bag /Jr=jar HV=high viscosity LV=low viscosity"""


async def _groq_parse(description: str) -> dict:
    resp = await _groq.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": PARSE_SYSTEM},
            {"role": "user",   "content": f"Parse:\n{description}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=250,
    )
    try:
        return json.loads((resp.choices[0].message.content or "").strip())
    except Exception:
        return {}


async def _parse_description(description: str, log) -> dict:
    description = _fix_unicode(description)
    local = _parse_local(description)
    log("info", "   [parse] Groq → local fallback...")
    try:
        result = await asyncio.wait_for(_groq_parse(description), timeout=20.0)
        if result and result.get("parse_confidence", 0) > 0.5:
            groq_brand = result.get("brand")
            if groq_brand and groq_brand.lower() not in description.lower():
                result["brand"] = local.get("brand")
            if not (result.get("search_query") or "").strip():
                result["search_query"] = local["search_query"]
            log("info", f"   [parse] ✓ \"{result.get('search_query','')}\" ({int(result.get('parse_confidence',0)*100)}%)")
            await asyncio.sleep(_PARSE_DELAY)
            return result
    except asyncio.TimeoutError:
        log("warn", "   [parse] ⚠ Groq timeout → local regex")
    except RateLimitError:
        log("warn", "   [parse] ⚠ Groq rate limit → local regex")
    except Exception as e:
        log("warn", f"   [parse] ⚠ Groq error → local regex ({str(e)[:40]})")

    log("info", f"   [parse] 📐 local \"{local['search_query']}\"")
    return local


# ─── Firecrawl: search ────────────────────────────────────────────────────────

def _fc_response_data(result) -> list[dict]:
    """Normalize Firecrawl search response (dict or pydantic model)."""
    if result is None:
        return []
    if isinstance(result, dict):
        if result.get("success") is False:
            return []
        data = result.get("data")
        return data if isinstance(data, list) else []
    if getattr(result, "success", False):
        return result.data or []
    return []


def _fc_response_markdown(result) -> str | None:
    """Normalize Firecrawl scrape response to markdown string."""
    if result is None:
        return None
    if isinstance(result, dict):
        if result.get("success") is False:
            return None
        if result.get("markdown"):
            return result["markdown"]
        data = result.get("data")
        if isinstance(data, dict) and data.get("markdown"):
            return data["markdown"]
        return None
    return getattr(result, "markdown", None) or None


async def _heartbeat_while(coro, on_tick, interval: float = 3.0):
    """Run *coro* while calling *on_tick(n, elapsed_secs)* every *interval* seconds."""
    task = asyncio.create_task(coro)
    tick = 0
    while not task.done():
        done_set, _ = await asyncio.wait({task}, timeout=interval)
        if task in done_set:
            break
        tick += 1
        on_tick(tick, tick * interval)
    return await task


async def _fc_search(fc: AsyncV1FirecrawlApp, query: str, log) -> list[dict]:
    """
    Firecrawl search — returns up to 5 results with title, URL, description.
    1 credit per call.
    """
    try:
        result = await asyncio.wait_for(
            fc.search(
                query,
                limit=5,
                lang="en",
                country="us",
                timeout=25000,
            ),
            timeout=30.0,
        )
        return _fc_response_data(result)
    except asyncio.TimeoutError:
        log("warn", "   ⚠ Firecrawl search timed out")
        return []
    except Exception as e:
        err = str(e)
        if "402" in err or "insufficient" in err.lower():
            log("warn", "   ⚠ Firecrawl credits exhausted (HTTP 402) — top up at firecrawl.dev")
        elif "401" in err or "unauthorized" in err.lower():
            log("error", "   ❌ Firecrawl API key invalid (HTTP 401)")
        elif "429" in err:
            log("warn", "   ⚠ Firecrawl rate limited — waiting 10s...")
            await asyncio.sleep(10)
        else:
            log("warn", f"   ⚠ Firecrawl search error: {err[:80]}")
        return []


# ─── Firecrawl: scrape single product page ───────────────────────────────────

async def _fc_scrape(fc: AsyncV1FirecrawlApp, url: str, query: str, log) -> str | None:
    """
    Scrape a product page with Firecrawl to get the exact price.
    Returns markdown content, or None on failure.
    1 credit per call. Renders JS, handles anti-bot protections.
    """
    try:
        result = await asyncio.wait_for(
            fc.scrape_url(
                url,
                formats=["markdown"],
                only_main_content=True,
                block_ads=True,
                timeout=_SCRAPE_TIMEOUT,
            ),
            timeout=35.0,
        )
        return _fc_response_markdown(result)
    except asyncio.TimeoutError:
        log("warn", f"   ⚠ Scrape timed out: {url[:60]}")
        return None
    except Exception as e:
        err = str(e)
        if "402" in err:
            log("warn", "   ⚠ Firecrawl credits exhausted")
        elif "429" in err:
            await asyncio.sleep(5)
        return None


# ─── Build PriceResult from search hit + optional scraped content ─────────────

def _build_price_result(
    item: LineItem,
    url: str,
    title: str,
    content: str,
    query: str,
    source: str,
    schein_price: float,
    schein_pack_qty: int | None,
    parsed: dict | None = None,
    is_fallback: bool = False,
    require_page: bool = False,
) -> PriceResult | None:
    """Extract price, validate page, score match, return PriceResult."""
    if _is_blocked(url, title):
        return None
    if _is_non_dental_product_hit(title, url, content, item.description_raw):
        return None
    if is_fallback and not _is_relevant_title(title, query):
        return None
    if _page_is_error(content, title) or _page_is_unavailable(content, title):
        return None

    match_text = _product_match_text(title, content)

    if not is_fallback and _page_pack_conflicts(schein_pack_qty, title, content):
        return None

    price = _extract_price(title, content, query)
    if price is None:
        return None
    if _is_variable_price_page(content) and schein_pack_qty:
        if _page_pack_conflicts(schein_pack_qty, title, content):
            return None
    if _is_suspicious_price(price, schein_price):
        return None

    pack_mismatch, pack_note = _check_pack_mismatch(
        schein_pack_qty, title, price, schein_price, content,
    )

    pr = PriceResult(
        line_item_id=item.line_number,
        supplier=_supplier_from_url(url),
        price=price,
        url=url,
        raw_text=match_text,
        source=source,
        match_reasoning="Firecrawl verified product page",
    )
    if pack_mismatch and pack_note:
        pr.pack_condition_note = pack_note

    if is_fallback:
        equiv_entries = [
            e for e in load_equivalency_table()
            if e.get("schein_sku") == item.schein_sku
        ]
        equiv_entry = equiv_entries[0] if equiv_entries else None
        local = _score_equiv_alternate_match(item, pr, query, equiv_entry)
    else:
        local = _score_exact_input_match(item, pr)

    mt = local.get("match_type", "no_match")

    if pack_mismatch and mt == "exact":
        mt = "pack_mismatch"
        local = {**local, "match_type": "pack_mismatch",
                 "matched_pack_qty": False,
                 "reasoning": local.get("reasoning", "") + " · pack size differs"}

    if mt == "no_match":
        return None

    pr.match_type           = mt
    pr.match_confidence     = local.get("confidence", 0.0)
    pr.matched_brand        = local.get("matched_brand", False)
    pr.matched_product_name = local.get("matched_product_name", False)
    pr.matched_form         = local.get("matched_form", False)
    pr.matched_pack_qty     = local.get("matched_pack_qty", False)
    pr.match_reasoning      = format_match_reasoning(item, local)
    return pr


def _pick_top_three(results: list[PriceResult], *, prefer_match: bool = True) -> list[PriceResult]:
    """Up to 3 unique URLs — best match quality first, then cheapest price."""
    pool = [r for r in results if r.price is not None and r.url]
    if not pool:
        return []
    type_order = {"exact": 0, "pack_mismatch": 1, "approximate": 2}
    if prefer_match:
        confirmed = [r for r in pool if r.match_type in ("exact", "pack_mismatch")]
        pool = confirmed or pool
    pool.sort(key=lambda r: (
        0 if r.matched_pack_qty else 1,
        type_order.get(r.match_type, 9),
        -(r.match_confidence or 0),
        r.price,
    ))
    picked: list[PriceResult] = []
    seen: set[str] = set()
    for r in pool:
        if r.url in seen:
            continue
        seen.add(r.url)
        picked.append(r)
        if len(picked) >= _EXACT_TARGET:
            break
    return picked


def _match_score_label(r: PriceResult) -> str:
    labels = {"exact": "EXACT", "pack_mismatch": "CLOSE", "approximate": "APPROXIMATE"}
    lbl = labels.get(r.match_type or "", "UNKNOWN")
    return f"{lbl} ({(r.match_confidence or 0):.0%})"


# ─── Per-item search + scrape pipeline ───────────────────────────────────────

async def _search_and_scrape_item(
    fc: AsyncV1FirecrawlApp,
    item: LineItem,
    parsed: dict,
    log,
    *,
    emit_progress=None,
    item_index: int = 1,
    item_total: int = 1,
    item_pct=None,
) -> tuple[list[PriceResult], list[PriceResult], str, str]:
    """
    File 1 — exact/almost-exact input search → up to 3 verified prices
    File 2 — parsed-query search ONLY when File 1 is empty
    """
    raw_fixed      = _fix_unicode(item.description_raw.strip())
    raw_query      = _make_raw_input_query(raw_fixed)
    clean_query    = _make_exact_query(raw_fixed, parsed)
    fallback_qs    = _fallback_queries(parsed, item.description_raw)
    fallback_query = fallback_qs[0] if fallback_qs else clean_query
    seen_urls: set[str] = set()

    def progress(substep: str, label: str, phase: float, detail: str = ""):
        if not emit_progress or not item_pct:
            return
        emit_progress({
            "step": 2,
            "pct": item_pct(phase),
            "label": f"Item {item_index}/{item_total}: {label}",
            "item_index": item_index,
            "item_total": item_total,
            "substep": substep,
            "detail": detail or label,
        })

    schein_pack_qty = None
    if item.description_parsed and item.description_parsed.pack_qty:
        schein_pack_qty = int(item.description_parsed.pack_qty)

    # ── File 1: full raw input first, then cleaned variants ───────────────────
    exact_pool: list[PriceResult] = []
    search_queries: list[str] = []
    for q in (raw_query, *_pack_search_queries(parsed), clean_query, clean_query + " dental supply"):
        q = q.strip()
        if q and q.lower() not in {x.lower() for x in search_queries}:
            search_queries.append(q)
    if "-" in clean_query:
        alt = clean_query.replace("-", " ")
        if alt.strip() and alt.lower() not in {x.lower() for x in search_queries}:
            search_queries.insert(2, alt.strip())

    async def process_hit(hit: dict, query: str, source: str, is_fallback: bool) -> PriceResult | None:
        url   = (hit.get("url") or "").strip()
        title = (hit.get("title") or "").strip()
        if not url.startswith("http") or url in seen_urls:
            return None
        if _is_blocked(url, title):
            return None
        snippet = hit.get("markdown") or hit.get("description") or hit.get("content") or ""
        if _is_non_dental_product_hit(title, url, snippet, item.description_raw):
            return None

        seen_urls.add(url)

        host = url.split("/")[2] if "/" in url else url
        progress(
            "scrape",
            f"Reading product page on {host}…",
            0.45 + 0.35 * min(len(seen_urls), 5) / 5,
            f"Scraping supplier page: {url[:80]}",
        )
        log("info", f"   📄 Scraping: {url}")
        page_content = await _heartbeat_while(
            _fc_scrape(fc, url, query, log),
            lambda tick, secs: progress(
                "scrape",
                f"Reading {host} ({int(secs)}s)…",
                0.45 + 0.35 * min(len(seen_urls), 5) / 5 + min(0.02 * tick, 0.04),
                f"Scraping supplier page: {url[:80]}",
            ),
        )
        content = page_content or snippet
        if not page_content and not snippet:
            log("info", f"   ⛔ Skipped (page unavailable): \"{title[:50]}\"")
            return None

        # Score against full input for File 1, parsed query for File 2
        score_query = item.description_raw if not is_fallback else query
        result = _build_price_result(
            item, url, title, content, score_query, source,
            item.unit_price, schein_pack_qty, parsed,
            is_fallback=is_fallback,
        )
        if result and result.price is not None:
            progress(
                "price_found",
                f"Found ${result.price:.2f} from {result.supplier}",
                0.55 + 0.25 * min(len(exact_pool), 3) / 3,
                f"Price ${result.price:.2f} on {result.supplier} — {title[:50]}",
            )
        return result

    progress(
        "search",
        "Building search queries from product description…",
        0.38,
        f"Prepared {len(search_queries)} search queries for this item",
    )

    for i, q in enumerate(search_queries):
        if _file1_search_complete(exact_pool, item):
            break
        if i == 0:
            label = "Exact input"
        elif i == 1:
            label = "Exact search (cleaned)"
        else:
            label = "Retry"
        progress(
            "search",
            f"Web search — {label}…",
            0.40 + 0.30 * (i / max(len(search_queries), 1)),
            f'Searching Google via Firecrawl: "{q[:70]}"',
        )
        log("info", f"   🔍 {label}: \"{q[:70]}\"")
        if i > 0:
            await asyncio.sleep(_SEARCH_DELAY)
        search_phase = 0.40 + 0.30 * (i / max(len(search_queries), 1))

        async def _do_search():
            return await _fc_search(fc, q, log)

        hits = await _heartbeat_while(
            _do_search(),
            lambda tick, secs: progress(
                "search",
                f"Firecrawl searching — {label} ({int(secs)}s)…",
                search_phase + min(0.02 * tick, 0.06),
                f'Waiting for Firecrawl API — query: "{q[:60]}"',
            ),
        )
        log("info", f"   ✓ {len(hits)} search results")
        progress(
            "search",
            f"Reviewing {len(hits)} search results…",
            0.42 + 0.30 * (i / max(len(search_queries), 1)),
            f"Found {len(hits)} pages — checking top results for prices",
        )

        sem = asyncio.Semaphore(3)

        async def bounded(h, query=q):
            async with sem:
                return await process_hit(h, query, "web_search_exact", False)

        results = await asyncio.gather(*[bounded(h) for h in hits[:5]], return_exceptions=False)
        for r in results:
            if r is not None:
                exact_pool.append(r)

    file1_results = _pick_top_three(exact_pool)

    if file1_results:
        best = min(file1_results, key=lambda r: r.price)
        log("info", (
            f"   ★ Best: ${best.price:.2f} from {best.supplier} "
            f"[{_match_score_label(best)}]"
        ))

    # ── File 2: parsed query ONLY when File 1 empty ────────────────────────────
    fallback_results: list[PriceResult] = []
    if not file1_results:
        log("info", "   ↪ No exact matches — parsed-query alternate search...")
        progress(
            "search",
            "No exact match — trying alternate search queries…",
            0.75,
            "Exact search returned nothing; running fallback parsed-query search",
        )
        for fq in fallback_qs:
            if len(fallback_results) >= _EXACT_TARGET:
                break
            progress(
                "search",
                "Alternate supplier search…",
                0.78,
                f'Fallback search: "{fq[:70]}"',
            )
            log("info", f"   🔍 Alternate: \"{fq}\"")
            await asyncio.sleep(_SEARCH_DELAY)
            fb_hits = await _fc_search(fc, fq, log)
            for hit in fb_hits:
                if len(fallback_results) >= _EXACT_TARGET:
                    break
                r = await process_hit(hit, fq, "web_search_fallback", True)
                if r is not None:
                    fallback_results.append(r)
        fallback_results = _pick_top_three(fallback_results, prefer_match=False)

    log("info", (
        f"   ✓ File1: {len(file1_results)} results · "
        f"File2: {len(fallback_results)} alternate results"
    ))

    return file1_results, fallback_results, raw_query, fallback_query


# ─── Main intelligence layer ──────────────────────────────────────────────────

class IntelligenceLayer:
    async def process(
        self,
        line_items: list[LineItem],
        emit=None,
        order_meta: dict | None = None,
    ) -> tuple[
        list[LineItem],
        dict[int, list[PriceResult]],
        list[WebSweepResult],
        dict[int, str],
    ]:
        supplier_results: dict[int, list[PriceResult]] = {
            it.line_number: [] for it in line_items
        }
        sweep_results:  list[WebSweepResult] = []
        search_queries: dict[int, str]       = {}

        def log(level: str, msg: str):
            print(f"[intel] {msg}")
            if emit:
                emit("log", {"level": level, "message": msg})

        total = len(line_items)

        if not _fc_key:
            log("error",
                "❌ FIRECRAWL_API_KEY not set in .env\n"
                "   Get free key (500 pages/month): https://www.firecrawl.dev\n"
                "   Then add: FIRECRAWL_API_KEY=fc-your_key_here")
            return line_items, supplier_results, sweep_results, search_queries

        fc = AsyncV1FirecrawlApp(api_key=_fc_key)
        log("info", (
            f"🚀 {total} items · Firecrawl search + scrape · "
            f"exact product pages · accurate prices\n"
            f"   Credits per order: ~{total} searches + up to {total * _EXACT_TARGET} scrapes"
        ))

        valid_pd = ParsedDescription.model_fields.keys()

        def item_pct(idx: int, phase: float) -> int:
            """Map item progress into step-2 range 20–71%. phase is 0.0–1.0 within item."""
            frac = (idx + phase) / max(total, 1)
            return min(71, 20 + int(frac * 52))

        def emit_progress(data: dict):
            if order_meta:
                data = {**order_meta, **data}
            if emit:
                emit("progress", data)

        # Immediately signal first item so UI moves past 20%
        if total > 0:
            emit_progress({
                "step": 2,
                "pct": 21,
                "label": f"Item 1/{total}: Starting price intelligence…",
                "item_index": 1,
                "item_total": total,
                "substep": "starting",
                "detail": f"Beginning analysis of {total} line items from this order",
            })

        for idx, item in enumerate(line_items):
            product_label = item.description_raw[:55]

            emit_progress({
                "step": 2,
                "pct": item_pct(idx, 0.05),
                "label": f"Item {idx + 1}/{total}: Parsing description with AI…",
                "item_index": idx + 1,
                "item_total": total,
                "substep": "parse",
                "detail": f"Groq AI is reading: \"{product_label}\"",
                "item_description": product_label,
            })
            log("info", f"━━ Item {idx+1}/{total}: {item.description_raw[:65]}")

            # Parse description (Groq — can take 10–20s)
            async def _do_parse():
                return await _parse_description(item.description_raw, log)

            parsed = await _heartbeat_while(
                _do_parse(),
                lambda tick, secs: emit_progress({
                    "step": 2,
                    "pct": min(item_pct(idx, 0.05 + min(0.08, 0.02 * tick)), item_pct(idx, 0.18)),
                    "label": f"Item {idx + 1}/{total}: AI parsing description ({int(secs)}s)…",
                    "item_index": idx + 1,
                    "item_total": total,
                    "substep": "parse",
                    "detail": f"Groq AI reading: \"{product_label}\"",
                    "item_description": product_label,
                }),
            )
            item.description_parsed = ParsedDescription(
                **{k: v for k, v in parsed.items() if k in valid_pd}
            )
            pd = item.description_parsed
            parts = [p for p in [
                f"brand={pd.brand}"                               if pd.brand        else None,
                f"product={pd.product_name[:25]}"                 if pd.product_name else None,
                f"pack={int(pd.pack_qty)}{pd.pack_unit or ''}"    if pd.pack_qty     else None,
            ] if p]
            parse_summary = ", ".join(parts) or "description only"
            log("info", f"   📐 {parse_summary}")

            emit_progress({
                "step": 2,
                "pct": item_pct(idx, 0.20),
                "label": (
                    f"Item {idx + 1}/{total}: Parsed — "
                    f"{pd.product_name[:35] if pd.product_name else 'searching by description'}"
                ),
                "item_index": idx + 1,
                "item_total": total,
                "substep": "parsed",
                "detail": f"Identified: {parse_summary}",
                "item_description": product_label,
            })

            emit_progress({
                "step": 2,
                "pct": item_pct(idx, 0.30),
                "label": f"Item {idx + 1}/{total}: Searching supplier websites…",
                "item_index": idx + 1,
                "item_total": total,
                "substep": "search",
                "detail": (
                    f"Firecrawl will search the web and scrape product pages for "
                    f"\"{pd.product_name or product_label[:40]}\""
                ),
                "item_description": product_label,
            })

            # Search + scrape
            exact_results, fallback_results, exact_q, fallback_q = \
                await _search_and_scrape_item(
                    fc, item, parsed, log,
                    emit_progress=emit_progress,
                    item_index=idx + 1,
                    item_total=total,
                    item_pct=lambda phase: item_pct(idx, phase),
                )
            search_queries[item.line_number] = fallback_q

            price_count = len(exact_results) + len(fallback_results)
            emit_progress({
                "step": 2,
                "pct": item_pct(idx, 1.0),
                "label": (
                    f"Item {idx + 1}/{total}: "
                    f"{'✓ ' + str(price_count) + ' price(s) found' if price_count else '✗ No prices found'}"
                ),
                "item_index": idx + 1,
                "item_total": total,
                "substep": "done" if price_count else "no_results",
                "detail": (
                    f"Finished item {idx + 1}: {price_count} verified price(s)"
                    if price_count
                    else f"No public prices found for item {idx + 1}"
                ),
                "item_description": product_label,
                "prices_found": price_count,
            })

            # Log all results
            for pr in exact_results:
                log("info", (
                    f"   💲 [File1] {pr.supplier}: ${pr.price:.2f}  "
                    f"[{_match_score_label(pr)}]  {(pr.raw_text or '')[:45]}\n"
                    f"      🔗 {pr.url or '—'}"
                ))
            for pr in fallback_results:
                log("info", (
                    f"   💲 [File2] {pr.supplier}: ${pr.price:.2f}  "
                    f"[{_match_score_label(pr)}]  {(pr.raw_text or '')[:45]}\n"
                    f"      🔗 {pr.url or '—'}"
                ))
            if not exact_results and not fallback_results:
                log("warn", f"   ⚠ No results found for \"{exact_q[:60]}\"")

            supplier_results[item.line_number] = exact_results + fallback_results

            best = exact_results[0] if exact_results else \
                   (fallback_results[0] if fallback_results else None)
            sweep_results.append(WebSweepResult(
                line_item_id=item.line_number,
                query_used=exact_q,
                price=best.price if best else None,
                url=best.url if best else None,
                site_name=best.supplier if best else None,
                raw_snippet=f"{_match_score_label(best)} — {best.raw_text or ''}" if best else "",
            ))

            if idx < total - 1:
                await asyncio.sleep(_ITEM_DELAY)

        total_prices = sum(1 for v in supplier_results.values() for r in v if r.price)
        log("info", f"✅ Done — {total_prices} verified prices across {total} items")

        return line_items, supplier_results, sweep_results, search_queries