# Dental Price Matcher — Portfolio Description

## One-Liner
AI-powered dental supply price comparison platform that turns Henry Schein order PDFs into automated savings reports in under 2 minutes.

## Summary
Dental Price Matcher is a full-stack procurement intelligence tool built for dental practice consultants. It automates the tedious process of comparing dental supply prices across competitors. Users upload a Henry Schein order confirmation PDF, and the system extracts every line item, searches 77+ supplier websites for competitive pricing, validates matches using AI, and generates formatted Excel reports showing potential savings — typically identifying ~35% in cost reductions.

## Problem
Dental practices order supplies through Henry Schein, one of the industry's largest distributors, but Schein's pricing isn't always competitive. Manually comparing prices across dozens of dental supply websites for every line item is tedious, error-prone, and takes hours — time dental office managers don't have.

## Solution
An end-to-end automated pipeline that:
1. Parses order PDFs using PyMuPDF with regex-based structured extraction
2. Enriches product data with AI (brand, product name, pack size, search queries)
3. Searches Google Shopping, organic results, and paid ads via SerpAPI
4. Scrapes competitor product pages with Firecrawl (full JS rendering)
5. Validates matches using LLM-powered 4-criteria trust checks (brand, product, size/form, pack qty)
6. Generates 3 Excel reports: Price Match, Alternate Purchases, and Evidence

## Key Features
- **Intelligent PDF Parsing**: Regex-based structured extraction from Henry Schein order PDFs with OCR fallback for scanned documents
- **Multi-LLM Support**: Groq (Llama 3.3 70B), Google Gemini 2.0 Flash, GPT-4o, OpenRouter — hot-swappable via env config
- **Multi-Query Search Strategy**: Brand-specific + generic queries to cover house brands (Acclean, Maxima, Criterion) that no competitor sells under the same name
- **AI-Powered Price Validation**: Four trust criteria validated by LLM against real scraped data — no hardcoded confidence scores
- **Cross-Brand Equivalency Matching**: Surfaces cheaper alternatives from different brands for the same product type
- **Marketplace Integration**: Dedicated Amazon and Walmart price rows with strict same-product matching
- **Real-Time Progress**: SSE streaming of pipeline events to the React dashboard (step status, API health, per-item updates)
- **Multi-Key API Rotation**: Automatic failover across multiple SerpAPI and Firecrawl keys with budget tracking
- **Smart Caching**: SQLite-backed discovery cache (7-day TTL) and scrape cache to minimize API credit consumption
- **77+ Supplier Sites**: Curated list of dental-specific online retailers plus marketplace coverage

## Tech Stack
- **Backend**: Python 3.12, FastAPI, Uvicorn, PyMuPDF, openpyxl, SQLite
- **Frontend**: React 18, TypeScript, Vite, SSE streaming
- **AI/LLM**: Groq (Llama 3.3 70B), Google Gemini 2.0 Flash, GPT-4o, OpenRouter
- **APIs**: SerpAPI (Google Search + Shopping), Firecrawl (JS page scraping)
- **Infrastructure**: Render (API), Vercel (Frontend), Docker, SQLite persistent cache
- **Reports**: openpyxl — 3 color-coded Excel workbooks per order

## Architecture Highlights
- Decoupled frontend (React/Vercel) and backend (FastAPI/Render) via REST + SSE
- Multi-stage pipeline with parallel item processing and per-item timeout guards
- SQLite discovery + scrape cache to conserve API credits across runs
- Configurable supplier list with excluded domain filtering
- MPN (Manufacturer Part Number) lookup table for enriched product identification
- Admin portal with authentication, order history, settings, and downloadable reports

## Generated Reports
1. **Price Match Report** — 16-column layout: SKU, description, best public price, match confidence, source site, product URL, pack/qty notes, Schein price, best price, savings per unit, total savings, plus marketplace rows
2. **Alternate Purchases** — curated buy list of only the best verified matches, ready for procurement
3. **Evidence File** — full audit trail: every candidate discovered, scraped data, AI validation scores, rejection reasons

## My Role
Full-stack developer and architect. Designed and built the entire system end-to-end — from PDF parsing and AI integration to the React admin dashboard and deployment infrastructure. This is a client-facing production tool actively used by dental practice consultants.

## Live Links
- Frontend: https://dental-price-matcher.vercel.app
- API: https://dental-price-matcher-fv3x.onrender.com
- GitHub: https://github.com/laiba18/dental-price-matcher
