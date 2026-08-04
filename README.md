# 🐦 Myna — Paas me kya khaane ko mil raha hai

*Thela, tapri, chaat corner, dhaba — jo kisi delivery app pe nahi hai.*

Myna answers one question: **what street food can I get near me, right now?** Zomato and Swiggy list restaurants. Nobody lists the momos cart outside the market gate, the chai tapri by the station, or the golgappe wala who parks in Gali 4 every evening — which is most of what India actually eats.

Three decisions hold the app together, and each one exists to kill a specific reason hyperlocal directories die:

| Decision | The failure it avoids |
|---|---|
| **Anyone can add anyone.** No vendor account, no login, no claim step first. | Directories that wait for shopkeepers to onboard themselves launch empty and stay empty. |
| **One photo is the whole add flow.** A food board *is* the menu and the price list, so a single frame gives the name, the kind and every dish. | Typing a menu is a form, and forms are where casual contributors quit. |
| **The street keeps data fresh, not the vendor.** Passers-by tap "Abhi hai ✓" / "Nahi mila ✕". | Vendors never update their own listings. Stale stock is what makes users stop trusting the app. |

Vendor phone numbers are deliberately never captured by the add flow — you can list a cart you walked past, but you can't publish that person's number without them.

## Quick start

```bash
./run.sh
```

Then open:
- **The food app:** http://localhost:8000
- **Owner panel:** http://localhost:8000/admin
- **API docs:** http://localhost:8000/docs

The original general-purpose product search (kirana, multi-item lists, dish→ingredients) is still served at **/classic** and **/shopkeeper** — see [General product search](#general-product-search-classic) below.

## The food app

### Home — "Kya khaana hai?"

GPS, a search box, and cards. Each card is a vendor: kind icon, distance, what's on the menu with prices, when it's there, how recently someone confirmed it, and one tap to Directions.

- **Search a dish** — "momos", "chai", "chole bhature". Matches the menu, the vendor's name and its kind together, so a cart called *Momo Point* that never listed an item still turns up.
- **Ranking is "what can I eat right now"** — open beats closed, a doubtful listing sinks, and only then does distance decide. Sorting purely by distance would put a Sunday-only cart above one standing at the corner.
- **Filters** — "Abhi khula 🔥" and a radius that cycles 3 → 10 → 1 km. A thela is a walk, not a drive.
- Hinglish in Roman script throughout — it's how the food is named out loud, it needs no font support on a cheap phone, and it's what people type.

### Add — one photo

Photo → GPS → listed. `ai.read_food_board` gets `{name, kind, items:[{name, price, category}]}` out of a single frame, because *"CHOWMEIN 40 / MOMOS 50"* is the shop name, the menu and the price list all at once. Prices are only ever read, never guessed — no number on the board means no price on the card.

Everything else is optional and behind a disclosure: a typed name if the board was unreadable, the vendor kind, and timings for a cart that moves (`day + start + end`, which creates a round via the existing stops model). A partial read still lists the vendor — throwing away a read menu to demand a retake is exactly the friction this flow removes.

### Freshness — the loop that keeps it alive

Every card carries "Aaj dekha gaya" / "3 din pehle dekha gaya" and two buttons. A "haan hai" is one tap: it bumps `seen_yes`, moves `last_seen_at`, and clears any "band hai" reported earlier that day — whoever is standing at the open shop is more current than whoever found it shut this morning.

A "nahi mila" asks **why**, because a cart being absent means three completely different things and treating them alike is what kills good listings — a chaat wala shut for one Tuesday would otherwise be voted down by exactly the people who like him most:

| Reason | Weight | What it does |
|---|---|---|
| **Aaj band hai** | 0 | Today's note only. Card shows "Aaj band bataya gaya" and sinks to the bottom **for today**; tomorrow it ranks normally again. Nothing is held against the listing. |
| **Yahan se hat gaya** | 1 | Argues this spot is wrong. Counts toward `doubtful`. |
| **Hamesha ke liye band** | 3 | Two of these retire the listing — `trust: "closed"`, dropped from search. |
| *(no reason given)* | 1 | Treated as a plain "nahi mila". |

A listing goes `doubtful` (faded, sunk) when the weighted total is ≥ 2 and exceeds `seen_yes`. Weights live in `food.SEEN_REASONS`, and the client fetches the reason list from `/api/food/kinds` rather than hardcoding one the backend scores differently.

### Reports — when the listing itself is wrong

The votes are about *today*; a report is about whether the listing should exist at all. The quiet ⚑ on each card flags it as fake, a joke, a duplicate, wrong info, or offensive.

**Three distinct devices hide a listing** from search — low enough that obvious junk goes fast, high enough that one annoyed person can't bury a competitor. One report per device, enforced by row rather than by counter.

Hiding is reversible and **never deletes**. Flagged listings go to the **Reports** tab in the owner panel, which is the only place that decision gets reviewed by a person:

- Reasons are broken down rather than summed — three "duplicate" is a merge, three "fake" is a delete, and one number can't tell you which.
- Each card shows the counter-evidence next to the accusation: how many people confirmed the vendor is real, how many said it's shut for good, whether it was added anonymously. A listing four people vouched for and three flagged is a very different call from one nobody ever confirmed.
- **Restore & clear reports** is offered as prominently as Delete, and it clears the reports too — restoring without that would just re-hide the listing on the next stray tap.
- A red count sits on the tab and a dashboard tile appears whenever anything is pending, because a queue nobody can see is a queue nobody works.

### Food API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/food/near?lat&long&q&kind&radius_km&open_now&limit` | The home screen. No `q` = everything nearby |
| `POST` | `/api/food/add` | One-photo add (multipart: `photo`, `lat`, `long`, optional `name`/`kind`/`address`/`device_id`/`day_of_week`/`start_time`/`end_time`) |
| `GET` | `/api/food/{shop_id}?lat&long` | One vendor card |
| `POST` | `/api/food/{shop_id}/seen` | `{"yes": false, "reason": "closed_today"}` — the freshness vote |
| `POST` | `/api/food/{shop_id}/report` | `{"reason": "fake", "device_id": "…"}` — flag a bad listing |
| `POST` | `/api/food/{shop_id}/items` | Add one dish by hand, when the board wasn't readable |
| `GET` | `/api/food/kinds` | Vendor kinds, popular-dish chips, categories, and both reason lists |
| `GET` | `/api/admin/reports?hidden_only` | Owner review queue for flagged listings |
| `POST` | `/api/admin/shops/{id}/visibility` | Hide or restore a listing (restoring clears its reports) |

Vendor kinds and food categories live in `app/food.py` — thela, chaat, chinese, chai, dhaba, sweets, juice, bakery, tiffin, restaurant.

## General product search (`/classic`)

The original kirana-oriented app is unchanged and still mounted. Everything below this line describes it.

> 📱 For phone testing (camera + GPS require a secure context): serve over HTTPS or use a tunnel
> like `cloudflared tunnel --url http://localhost:8000` / `ngrok http 8000`, then open the tunnel URL on the phone.

### Features (original Phase 1 scope)

- **Thela / cart vendors (no fixed place)** — a vendor who moves around registers as a *thela* and adds **rounds** instead of one address: each round is a spot plus its timing ("Gali no. 4, har mangalwar 10 se 12", or every day 6–9 AM). Customers see the round they can actually reach — "Here now · till 12 PM" — with directions to that corner, plus the vendor's other rounds and when they come next. Search puts what you can buy right now first: fixed shops and carts standing at a stop, then today's rounds, then later in the week
- **Shop onboarding** — signage photo → AI reads shop name (Claude Vision), GPS auto-capture, address auto-filled via OpenStreetMap reverse geocoding, manual override everywhere
- **Item add (semi-auto)** — item photo → AI suggests name/category → shopkeeper confirms → listed as available
- **Item edit/delete** anytime
- **Two ways to search** — the landing screen asks how you want to look:
  - **Search items** — type what you need ("milk bread eggs", *"atta chawal aur namak"*)
  - **By dish** — type a dish ("paneer butter masala", "poha") and Myna turns it into the full ingredient shopping list, then finds who nearby stocks each one. The LLM plans the ingredients (grounded with web search); a curated glossary (`app/dishes.py`) covers ~50 common dishes so dish mode works with no API key at all.
- **Mobile-first UI** — white & yellow theme, transparent header so the content gets the full screen, bottom tab bar, tick-off shopping list, one-tap Directions/Call per shop, light + dark mode
- **Customer search** — multi-item agentic pipeline: the query is parsed into individual items (LLM, with rule-based fallback so it works without an API key), each item is fuzzy-matched across name/category/shop/shopkeeper/address, then results are aggregated per shop — shops that stock more of your list rank first, then nearest-first (Haversine). Handles multi-item and Hinglish queries: *"salt milk and mango"*, *"atta chawal aur namak"*
- **Owner panel** — dashboard stats (shops/items counts), shop list with search, inline edit/delete, and an AI settings screen organised by what each model is *for* (reading photos / understanding searches / matching similar words), with one save bar instead of a save button per field
- **Vision self-test** — model pickers mark which models can accept images, and "Test with a sample photo" sends a generated shop board with a random code on it and reports whether the model read it back. Picking a text-only model for OCR used to break every photo upload silently; now the panel says so up front
- **CSV import** — owner can download a blank template (or 50-shop demo dataset) and upload a filled CSV to bulk-create/update shops & items; optional "wipe existing data first"

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(empty)_ | Claude Vision for signage/item recognition. |
| `GROQ_API_KEY` | _(empty)_ | Groq Vision (e.g. Llama 4 Scout) for signage/item recognition. |
| `GEMINI_API_KEY` | _(empty)_ | Gemini Vision (e.g. 2.5 Flash) for signage/item recognition. |
| `MYNA_DATABASE_URL` | _(falls back to `DATABASE_URL`, then SQLite)_ | Postgres URL. Checked first; `DATABASE_URL` (auto-set by Render/Heroku) is the fallback. |
| `DATABASE_URL` | `sqlite:///./myna.db` | Postgres URL supplied by hosting platform, or a manual override. |
| `MYNA_TIMEZONE` | `Asia/Kolkata` | Timezone that thela/cart round timings are read in. |
| `UPLOAD_DIR` | `./uploads` | Where item/shop photos are stored. Swap for Cloudinary/Supabase in production. |

> **AI works without any API key** — name/category fields just stay manual. Set any provider key to enable AI suggestions.

## Project structure

```
app/
  main.py            FastAPI app, static/upload mounts
  food.py            Food vocabulary: vendor kinds, categories, Hinglish labels
  routers/food.py    One-photo add, "paas me kya hai", freshness votes
  static/khana.html  The food app UI (served at /)
  config.py          Env-driven settings
  database.py        SQLAlchemy engine/session
  models.py          shops + items tables
  schemas.py         Pydantic request/response models
  geo.py             Haversine distance + Nominatim reverse geocode
  schedule.py        Mobile-vendor rounds: "when is he here" + human timings
  ai.py              Multi-provider AI (Anthropic / Groq / Gemini) — vision + text
  agent.py           Agentic search pipeline: query→items parsing, dish/concept expansion (LLM + fallback)
  dishes.py          Curated dish→ingredients glossary (zero-config dish mode)
  vision_check.py    Generates a test shop board and checks a model really reads it
  storage.py         Image upload saving
  routers/
    shops.py         Shop CRUD, onboarding photo, geocode endpoint, vendor stops
    items.py         Item CRUD, AI suggest endpoint
    search.py        Customer search (item mode + dish mode, coverage ranking)
    admin.py         Owner panel API (stats, shop list, moderation, LLM status)
  static/
    index.html       Customer search page (mobile-first, item + dish modes)
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
| `GET/POST` | `/api/shops/{id}/stops` | List / add a mobile vendor's rounds (place + day + time window). Adding one marks the shop `mobile` |
| `PATCH/DELETE` | `/api/shops/{id}/stops/{stop_id}` | Edit / remove a round |
| `GET` | `/api/search/shops?q&lat&long&limit` | Agentic pipeline output grouped per shop (coverage score + matched items) |
| `GET` | `/api/search/one-tap?q&lat&long&limit` | Pipeline + instant shopping list (one product per requested item) |
| `POST` | `/api/shops/onboard/photo` | AI-read shop name from signage photo |
| `GET` | `/api/shops/geocode/reverse?lat&long` | GPS → address |
| `GET/POST` | `/api/shops/{id}/items` | List / add items (multipart: name, category, photo) |
| `PATCH/DELETE` | `/api/shops/{id}/items/{item_id}` | Edit / remove item |
| `POST` | `/api/shops/{id}/items/suggest` | AI-suggest item name/category from photo |
| `GET` | `/api/search?q&lat&long&limit` | Agentic search — parses query into items, matches each, groups+scores per shop (coverage-first, then nearest) |
| `GET` | `/api/search/shops?q&lat&long&limit&mode` | Same pipeline, returned as one card per shop with matched items + coverage (e.g. "2/3 items here"). `mode=dish` expands a dish name into its ingredients first |
| `GET` | `/api/search/one-tap?q&lat&long&limit&mode` | Pipeline plus a ready shopping list — one best product per requested item from the nearest shop that stocks it. `mode=dish` treats `q` as a dish name and expands it into ingredients first |
| `GET` | `/api/search/dishes?limit` | Popular dish suggestions for the app's dish-mode chips |
| `GET` | `/api/admin/stats` | Owner dashboard stats (shop/item counts, recent shops) |
| `GET` | `/api/admin/shops?q` | List/search all shops |
| `GET/PATCH/DELETE` | `/api/admin/shops/{id}` | Shop detail / update / delete |
| `GET` | `/api/admin/shops/{id}/items` | Items for a shop |
| `PATCH/DELETE` | `/api/admin/items/{id}` | Edit / remove any item |
| `GET` | `/api/admin/llm/providers` | Configured AI providers and default model |
| `GET` | `/api/admin/llm/models` | Fetch available chat models from configured providers, each tagged with whether it accepts images |
| `POST` | `/api/admin/llm/vision-test` | Send a generated shop-board image to a model and report whether it read the code back (`pass` / `partial` / `no_vision` / `error`) |
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

**Food app**

- No claim flow yet — a vendor can't take over their own listing, which is what should unlock the phone-number field.
- `device_id` is an anonymous localStorage string. It stops accidental double-voting and one-person report floods, but clearing storage mints a new id, so it isn't real abuse resistance — that needs a server-side signal.
- "Aaj band hai" is a single flag, not a history, so a vendor shut every Monday looks the same as one shut once. Repeated closures on the same weekday should eventually become a schedule.
- Reports are counted but not weighted by reporter — three throwaway devices hide a listing as effectively as three real ones.

**General search**

- Shopkeeper "auth" is just a `localStorage` shop_id — fine for single-device pilot onboarding, needs real auth before wider rollout.
- Vendor rounds are a weekly pattern (day + time window) — no one-off "aaj nahi aa raha" override, and no live GPS tracking; the card shows the schedule the vendor typed.
- Item matching is substring-based (`ILIKE %q%`); upgrade to trigram/tsvector search when catalogue grows.
- SQLite for local dev; set `DATABASE_URL` to Postgres for deployment (Haversine runs in Python, so no PostGIS needed).
- Nominatim is rate-limited (~1 req/s) — fine at MVP volume.
