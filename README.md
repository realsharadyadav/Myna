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
- **Customer search** — fuzzy text match across item name, category, shop name, shopkeeper name & address, results sorted nearest-first (Haversine)
- **Owner panel** — dashboard stats (shops/items counts), shop list with search, inline edit/delete, LLM provider + model selector (default saved in DB)

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
  ai.py              Multi-provider Vision AI (Anthropic / Groq / Gemini)
  storage.py         Image upload saving
  routers/
    shops.py         Shop CRUD, onboarding photo, geocode endpoint
    items.py         Item CRUD, AI suggest endpoint
    search.py        Customer search (fuzzy + distance filter)
    admin.py         Owner panel API (stats, shop list, moderation, LLM status)
  static/
    index.html       Customer search page (mobile-first)
    shopkeeper.html  Shop onboarding + item management page
    admin.html       Owner dashboard (stats, shops, AI settings)
uploads/             Saved photos (gitignored)
run.sh               Creates venv, installs deps, starts uvicorn
```

## API summary

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/shops` | Register a shop (lat/long required; address auto-geocoded if blank) |
| `GET/PATCH` | `/api/shops/{id}` | Fetch / update shop |
| `POST` | `/api/shops/{id}/photo` | Upload shop signage photo |
| `POST` | `/api/shops/onboard/photo` | AI-read shop name from signage photo |
| `GET` | `/api/shops/geocode/reverse?lat&long` | GPS → address |
| `GET/POST` | `/api/shops/{id}/items` | List / add items (multipart: name, category, photo) |
| `PATCH/DELETE` | `/api/shops/{id}/items/{item_id}` | Edit / remove item |
| `POST` | `/api/shops/{id}/items/suggest` | AI-suggest item name/category from photo |
| `GET` | `/api/search?q&lat&long&limit` | Find matching items at any shop, nearest first (no range filter) |
| `GET` | `/api/admin/stats` | Owner dashboard stats (shop/item counts, recent shops) |
| `GET` | `/api/admin/shops?q` | List/search all shops |
| `GET/PATCH/DELETE` | `/api/admin/shops/{id}` | Shop detail / update / delete |
| `GET` | `/api/admin/shops/{id}/items` | Items for a shop |
| `PATCH/DELETE` | `/api/admin/items/{id}` | Edit / remove any item |
| `GET` | `/api/admin/llm/providers` | Configured AI providers and default model |
| `GET` | `/api/admin/llm/models` | Fetch all available vision models from configured providers |
| `POST` | `/api/admin/llm/default-model` | Set the default model (persisted in DB) |
| `GET` | `/admin` | Owner panel UI (dashboard, shops, AI settings) |

## Deploy to Render

One-click deploy using the included `render.yaml` blueprint:

1. Push this repo to GitHub, then in Render: **New → Blueprint** → select the repo.
2. Render creates the web service, a free PostgreSQL DB, and a 1 GB uploads disk automatically.
3. After deploy, go to the service's **Environment** tab and add your API keys (`ANTHROPIC_API_KEY` / `GROQ_API_KEY` / `GEMINI_API_KEY`) — they're marked `sync: false` in the blueprint.
4. Open `https://<your-service>.onrender.com/admin` to pick the default model.

SQLite (`myna.db`) is only for local dev — production uses Postgres via `DATABASE_URL` (auto-injected by Render), and uploads go to the persistent disk (`UPLOAD_DIR=/var/data/uploads`).

## Deferred (per plan)

Payments/monetization (Phase 3), full-auto shelf scanning, native mobile app (Phase 4).

## Known MVP limitations

- Shopkeeper "auth" is just a `localStorage` shop_id — fine for single-device pilot onboarding, needs real auth before wider rollout.
- Item matching is substring-based (`ILIKE %q%`); upgrade to trigram/tsvector search when catalogue grows.
- SQLite for local dev; set `DATABASE_URL` to Postgres for deployment (Haversine runs in Python, so no PostGIS needed).
- Nominatim is rate-limited (~1 req/s) — fine at MVP volume.
