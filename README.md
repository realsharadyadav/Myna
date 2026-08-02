# 🐦 Myna — Hyperlocal Shop & Product Finder

*"Yahan available hai" — Myna batayegi kahan.*

Phase 1 webapp MVP: shopkeepers list what's in stock with their phone camera; customers find nearby shops that have the product they need, within a range they set.

## Quick start

```bash
./run.sh
```

Then open:
- **Customer search:** http://localhost:8000
- **Shopkeeper onboarding:** http://localhost:8000/shopkeeper
- **Owner panel:** http://localhost:8000/admin
- **API docs:** http://localhost:8000/docs

> 📱 For phone testing (camera + GPS require a secure context): serve over HTTPS or use a tunnel
> like `cloudflared tunnel --url http://localhost:8000` / `ngrok http 8000`, then open the tunnel URL on the phone.

## Features (Phase 1 scope)

- **Shop onboarding** — signage photo → AI reads shop name (Claude Vision), GPS auto-capture, address auto-filled via OpenStreetMap reverse geocoding, manual override everywhere
- **Item add (semi-auto)** — item photo → AI suggests name/category → shopkeeper confirms → listed as available
- **Item edit/delete** anytime
- **Customer search** — multi-item agentic pipeline: the query is parsed into individual items (LLM, with rule-based fallback so it works without an API key), each item is fuzzy-matched across name/category/shop/shopkeeper/address, then results are aggregated per shop — shops that stock more of your list rank first, then nearest-first (Haversine). Handles multi-item and Hinglish queries: *"salt milk and mango"*, *"atta chawal aur namak"*
- **Owner panel** — dashboard stats (shops/items counts), shop list with search, inline edit/delete, LLM provider + model selector (default saved in DB)
- **CSV import** — owner can download a blank template (or 50-shop demo dataset) and upload a filled CSV to bulk-create/update shops & items; optional "wipe existing data first"

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(empty)_ | Claude Vision for signage/item recognition. |
| `GROQ_API_KEY` | _(empty)_ | Groq Vision (e.g. Llama 4 Scout) for signage/item recognition. |
| `GEMINI_API_KEY` | _(empty)_ | Gemini Vision (e.g. 2.5 Flash) for signage/item recognition. |
| `MYNA_DATABASE_URL` | _(falls back to `DATABASE_URL`, then SQLite)_ | Postgres URL. Checked first; `DATABASE_URL` (auto-set by Render/Heroku) is the fallback. |
| `DATABASE_URL` | `sqlite:///./myna.db` | Postgres URL supplied by hosting platform, or a manual override. |
| `UPLOAD_DIR` | `./uploads` | Where item/shop photos are stored. Swap for Cloudinary/Supabase in production. |

> **AI works without any API key** — name/category fields just stay manual. Set any provider key to enable AI suggestions.

## Project structure

```
app/
  main.py            FastAPI app, static/upload mounts
  config.py          Env-driven settings
  database.py        SQLAlchemy engine/session
  models.py          shops + items tables
  schemas.py         Pydantic request/response models
  geo.py             Haversine distance + Nominatim reverse geocode
  ai.py              Multi-provider AI (Anthropic / Groq / Gemini) — vision + text
  agent.py           Agentic search pipeline: query→items parsing (LLM + fallback)
  storage.py         Image upload saving
  routers/
    shops.py         Shop CRUD, onboarding photo, geocode endpoint
    items.py         Item CRUD, AI suggest endpoint
    search.py        Customer search (fuzzy + distance filter)
    admin.py         Owner panel API (stats, shop list, moderation, LLM status)
  static/
    index.html       Customer search page (mobile-first)
    shopkeeper.html  Shop onboarding + item management page
    admin.html       Owner dashboard (stats, shops, AI settings, CSV import)
  sample_data.py     Reusable demo data (curated + generated shops, CSV helpers)
uploads/             Saved photos (gitignored)
run.sh               Creates venv, installs deps, starts uvicorn
```

## API summary

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/shops` | Register a shop (lat/long required; address auto-geocoded if blank) |
| `GET/PATCH` | `/api/shops/{id}` | Fetch / update shop |
| `POST` | `/api/shops/{id}/photo` | Upload shop signage photo |
| `GET` | `/api/search/shops?q&lat&long&limit` | Agentic pipeline output grouped per shop (coverage score + matched items) |
| `GET` | `/api/search/one-tap?q&lat&long&limit` | Pipeline + instant shopping list (one product per requested item) |
| `POST` | `/api/shops/onboard/photo` | AI-read shop name from signage photo |
| `GET` | `/api/shops/geocode/reverse?lat&long` | GPS → address |
| `GET/POST` | `/api/shops/{id}/items` | List / add items (multipart: name, category, photo) |
| `PATCH/DELETE` | `/api/shops/{id}/items/{item_id}` | Edit / remove item |
| `POST` | `/api/shops/{id}/items/suggest` | AI-suggest item name/category from photo |
| `GET` | `/api/search?q&lat&long&limit` | Agentic search — parses query into items, matches each, groups+scores per shop (coverage-first, then nearest) |
| `GET` | `/api/search/shops?q&lat&long&limit` | Same pipeline, returned as one card per shop with matched items + coverage (e.g. "2/3 items here") |
| `GET` | `/api/search/one-tap?q&lat&long&limit` | Pipeline plus a ready shopping list — one best product per requested item from the nearest shop that stocks it |
| `GET` | `/api/admin/stats` | Owner dashboard stats (shop/item counts, recent shops) |
| `GET` | `/api/admin/shops?q` | List/search all shops |
| `GET/PATCH/DELETE` | `/api/admin/shops/{id}` | Shop detail / update / delete |
| `GET` | `/api/admin/shops/{id}/items` | Items for a shop |
| `PATCH/DELETE` | `/api/admin/items/{id}` | Edit / remove any item |
| `GET` | `/api/admin/llm/providers` | Configured AI providers and default model |
| `GET` | `/api/admin/llm/models` | Fetch all available vision models from configured providers |
| `POST` | `/api/admin/llm/default-model` | Set the default model (persisted in DB) |
| `GET` | `/api/admin/import/template?sample` | Download CSV template (blank, or `?sample=1` = 50 demo shops) |
| `POST` | `/api/admin/import/csv` | Import shops/items from CSV (multipart `file`; `replace=true` wipes existing first) |
| `GET` | `/admin` | Owner panel UI (dashboard, shops, AI settings, CSV import) |

### CSV import format

Flat — one row per item, shop fields repeated:

```csv
shop_name,shopkeeper,lat,long,address,phone,item_name,category
Sharma General Store,Ramesh Sharma,19.0760,72.8777,Shop 4 Link Rd Andheri West,9820012345,Parle-G Gold 100g,Snacks
```

Rows are grouped by `shop_name`: new names create a shop, existing names update it (only non-empty CSV fields overwrite). Every row with an `item_name` adds an item to its shop. Get the header right by downloading the template from the admin **Import CSV** tab.

## Deploy to Render (free plan)

One-click deploy using the included `render.yaml` blueprint:

1. Push this repo to GitHub, then in Render: **New → Blueprint** → select the repo.
2. Render creates the web service and a **free PostgreSQL DB** automatically.
3. After deploy, go to the service's **Environment** tab and add your API keys (`ANTHROPIC_API_KEY` / `GROQ_API_KEY` / `GEMINI_API_KEY`) — they're marked `sync: false` in the blueprint.
4. Open `https://<your-service>.onrender.com/admin` to pick the default model.

> **Free-tier notes:**
> - Uploads go to the app's local `uploads/` folder, which **resets on every redeploy** (no persistent disk on free plan). Fine for a pilot; attach a disk or switch to Cloudinary/Supabase when you need permanence.
> - The free Postgres DB expires after **90 days** — upgrade to a paid tier to keep it.
> - Service **sleeps after ~15 min idle**; first request takes ~30 s to wake up.
> - The blueprint injects `DATABASE_URL` automatically, which points to Postgres.

## Deferred (per plan)

Payments/monetization (Phase 3), full-auto shelf scanning, native mobile app (Phase 4).

## Known MVP limitations

- Shopkeeper "auth" is just a `localStorage` shop_id — fine for single-device pilot onboarding, needs real auth before wider rollout.
- Item matching is substring-based (`ILIKE %q%`); upgrade to trigram/tsvector search when catalogue grows.
- SQLite for local dev; set `DATABASE_URL` to Postgres for deployment (Haversine runs in Python, so no PostGIS needed).
- Nominatim is rate-limited (~1 req/s) — fine at MVP volume.
