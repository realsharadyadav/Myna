# 🐦 Myna — Paas me kya mil raha hai

*Thela, tapri, hardware, ghadi wala — jo kisi app pe nahi hai.*

Myna answers one question: **where do I get this near me?** Two versions of it, and the second is the one nothing else answers at all:

- *What street food is near me right now?* Zomato and Swiggy list restaurants. Nobody lists the momos cart outside the market gate or the golgappe wala who parks in Gali 4 every evening.
- *Which of these hundred shops has a water tanki — and who can still repair an old watch?* In a village you find out by walking, all day, asking. Google Maps indexes shops; it does not index what is inside them, and it has never indexed what they can **do**.

Four decisions hold the app together, and each one exists to kill a specific reason hyperlocal directories die:

| Decision | The failure it avoids |
|---|---|
| **Anyone can add anyone.** No vendor account, no login, no claim step first. | Directories that wait for shopkeepers to onboard themselves launch empty and stay empty. |
| **One photo is the whole add flow** — where there's a board to read. A food board *is* the menu and the price list, so a single frame gives the name, the kind and every dish. | Typing a menu is a form, and forms are where casual contributors quit. |
| **Capabilities are listed, not just stock.** "Ye ghadi theek karte hain" is a row, the same as a dish or a product. | Stock is true for a week; a capability is true for years. It costs nothing to keep accurate and it's the thing you genuinely cannot look up. |
| **Freshness applies only to things that go off.** The street confirms a thela with "Abhi hai ✓" / "Nahi mila ✕"; a hardware shop is never asked to re-prove it exists. | Ageing every listing would bury the only record of who stocks a water tanki under fresher listings that don't. |

Vendor phone numbers are deliberately never captured by the add flow — you can list a cart you walked past, but you can't publish that person's number without them.

### Families

Every vendor belongs to one family, and the family decides how its listing is ranked and kept fresh — see `app/food.py`.

| Family | Kinds | Presence |
|---|---|---|
| 🍽️ **Khaana** | thela, chaat, chinese, chai, dhaba, sweets, juice, bakery, tiffin, restaurant | **Perishable.** Open beats closed, an unconfirmed listing goes stale, "aaj band hai" sinks it for exactly one day. |
| 🛍️ **Saamaan** | kirana, hardware, electrical, electronics, medical, stationery, cloth, agri, sabzi | **Durable.** Ranked on match quality then distance — a shop stocking the one thing you searched for shouldn't sink because it's 8 PM. |
| 🔧 **Kaam** | repair, mobile repair, cycle, tailor, salon | **Durable**, same as above. |

`mobile` and `family` are independent: a sabzi thela moves like a food cart but sells goods.

## Quick start

```bash
./run.sh
```

Two processes, the same split as production — the API on `:8000`, the pages on `:5173`. `./run.sh api` and `./run.sh ui` run them separately.

- **The app:** http://localhost:5173
- **Village survey:** http://localhost:5173/survey.html
- **Owner panel:** http://localhost:5173/admin.html
- **API docs:** http://localhost:8000/docs

The backend serves no HTML. That's deliberate: it means there is exactly one way the UI reaches it, the same way a mobile app will.

## The app

### Home — "Kya chahiye?"

GPS, a search box, and cards. Each card is a jagah: kind icon, distance, what's on the menu with prices, when it's there, how recently someone confirmed it, and one tap to Directions.

- **Search a dish** — "momos", "chai", "chole bhature". Matches the menu, the jagah's name and its kind together, so a cart called *Momo Point* that never listed an item still turns up.
- **Several dishes at once** — "momos aur chawmin" returns two jagah, each shown for its own word: the momos cart for "momos", the chowmein cart for "chawmin". Matches are reported per *typed* word, so a card can say why it's there.
- **Ranking follows the family.** For a thela the question is "what can I get *right now*": open beats closed, a doubtful listing sinks, and only then does distance decide — sorting purely by distance would put a Sunday-only cart above one standing at the corner. For a shop or a capability the question is "who has this at all", so match quality and distance decide; a hardware shop carries no timings, and burying it at 8 PM would answer the wrong question. `open_now` therefore only filters the listings that know their own hours.
- **Filters** — "Abhi khula 🔥". Nothing is excluded for being far; distance only decides order, so the one shop in town that has what you need still shows up even from across the city.
- **Theme** — follows the phone, with a toggle that overrides it, shared with the owner panel through one `myna_theme` key. The override needs its own CSS rule rather than only a media query: an attribute set later can't beat `@media (prefers-color-scheme: dark)`, so a phone in dark mode ignored an explicit "light" entirely.
- Hinglish in Roman script throughout — it's how the food is named out loud, it needs no font support on a cheap phone, and it's what people type.

### Add — photos

Photos → GPS → listed. `ai.read_food_board` gets `{name, kind, items:[{name, price, category}]}` out of a single frame, because *"CHOWMEIN 40 / MOMOS 50"* is the shop name, the menu and the price list all at once. Prices are only ever read, never guessed — no number on the board means no price on the card.

**One photo is enough, more is better.** Two shots of one thela carry different halves of the truth: a wide one gets the signboard name, a close one gets the rates, a shot of the tawa gets dishes nobody ever wrote down. `ai.read_food_boards` reads each and merges them (`merge_boards`):

- **name** — first non-empty. Predictable beats clever: the screen says shoot the board first, and a "longest wins" rule would happily pick an invented *"Momos thela"* over a real *"Raju"*.
- **kind** — most common real kind across the photos; ties go to the earliest.
- **items** — the union, deduped by name. A duplicate dish keeps whichever copy carries a price, so the close-up's ₹40 survives the wide shot's priceless entry.
- One unreadable shot among several isn't a failure — it's the reason someone took more than one. An error comes back only when *nothing* was read from *any* photo.

**Camera or gallery.** Both buttons are on the add screen and both feed the same review step. They need separate `<input>`s: `capture="environment"` is what opens the camera directly, and it *skips the picker entirely* — so a single input carrying it makes the gallery unreachable, which is what used to happen while the screen said "ya gallery se choose karo". Someone who photographed a thela on the way home has to be able to add it when they get there.

**Photos are shrunk twice, for two different reasons.** The browser re-encodes to 1600px before uploading — five 4 MB photos over a 4G uplink is the slowest part of adding a jagah, long enough that people assume it hung and close the sheet. The server shrinks again in `app/images.py`: 1568px for the model (past which it reads nothing extra, and Anthropic rejects a base64 image over 5 MB outright) and 1280px for the copy that gets stored, since the card shows it a few hundred pixels wide and the rest is bandwidth on the viewer's mobile data. A real 3000×2000 phone photo lands at **55 KB stored, from 2.8 MB** — and the client-side pass alone cuts the upload 15×. EXIF orientation is applied and then stripped: a portrait photo carries its rotation as a flag rather than in the pixels, so re-encoding without honouring it delivers a sideways board. Stripping the rest also drops the GPS tags phones embed, which aren't ours to publish.

Capped at **5 photos** (`MAX_PHOTOS`): every extra one is another vision call, and five is well past the point where a thela has anything new to show. Only the first photo is kept when image retention is on — it's the one shown on the card; the rest were read for their text and have done their job.

Everything else is optional and behind a disclosure on the review screen: a typed name if the board was unreadable, the vendor kind, and timings for a cart that moves (`day + start + end`, which creates a round via the existing stops model). Those fields sit on the review screen and not the camera screen deliberately — you only find out the board was unreadable *after* submitting, and the error tells you to type a name, so the name field has to be reachable from where the error appears. A partial read still lists the vendor — throwing away a read menu to demand a retake is exactly the friction this flow removes.

### Add — the survey screen (`/survey.html`)

The photo flow reads a board. A hardware shop has no board listing its stock, and **nowhere does any shop advertise what it can repair** — so the information hardest to find is precisely the information no camera can capture. It gets typed, on the spot, by whoever walked in and asked.

This screen is built for one job: mapping a village on foot, shop by shop, in an afternoon.

- **Chip entry, not a form.** Type a word, press enter or comma, it's a chip and the box is ready for the next. Two boxes — *kya bikta hai* and *kya banta / theek hota hai* — which is the only place the product/service split is ever asked about explicitly. Elsewhere it's inferred from the name (`suggest_item_kind`), so "ghadi repair" lands as a service without anyone choosing.
- **GPS is re-fixed per shop**, automatically, after each save. Shops on one street are metres apart, and a stale fix would pile a whole bazaar onto one pin.
- **One request per shop, not per item** (`POST /api/food/survey`). The surveyor is on 2G.
- **It works with no network at all.** A save that can't reach the server is queued in `localStorage` and uploaded when the signal returns — automatically, or by tapping the banner. Losing an afternoon's walking is the thing that would stop someone doing a second one.
- **Re-sending is safe.** Items already on the shop (same name + kind, case-insensitive) are skipped, so a queued entry sent twice doesn't double the list. Passing `shop_id` adds to a shop already mapped instead of creating a second copy.
- The vendor-kind picker is **fetched from `/api/food/kinds`**, so the page holds no copy of the taxonomy — adding a kind server-side makes it appear here.

A shop added this way starts confirmed (`seen_yes = 1`, `last_seen_at` now): the person filling it in is standing in front of the place.

### Search — spelling, word boundaries, meaning

Four stages, cheapest first, because most searches never need the expensive one (`resolve_terms` in `routers/food.py`):

1. **The word itself.** Matched with `term_in`, which anchors to a word start rather than doing a plain substring check. That check was wrong in a way that's easy to miss: "tea" sits inside "S**tea**m Momos", so searching for tea returned a momos cart. Prefixes still work — "momo" finds "Momos", "samosa" finds "Samosas".
2. **Fuzzy correction** against the dish vocabulary *plus the dish names actually on menus nearby*, so a jagah selling something the built-in list never heard of is still reachable through a misspelling. Free, instant, and enough for "chawmin" → "chowmein". A term that's already known, or is a prefix of one, is left alone — guessing wrong silently searches for a different food.
3. **Synonyms** (`food.SYNONYM_GROUPS`) — the same food under a different name: *momos / dimsum / dumpling*, *golgappe / puchka / gupchup*, *anda / egg*, *machli / fish*. Spelling correction cannot do this; those words aren't misspellings of each other, they share no letters. For a vocabulary this small and this well known, a curated list is more reliable than a model — and it needs nothing to download. Matching is prefix-friendly, which makes short synonyms landmines: "cha" for chai matched every *Chaat* stall, "ras" for juice matched Rasgulla. Four characters is the floor, and a test asserts no synonym is a prefix of a dish in another group.
4. **An LLM**, but *only* for words the first three couldn't place ("chaomen", "gol gappay"). Paying for a model call on every search would be waste when "momos" needs no help. The model may only map onto dishes the app already knows; anything else is a hallucinated dish and gets dropped.

A category is a bucket, never a dish. "Chai & drinks" used to be a category name, which meant every juice stall matched a search for "chai" — search reads the category too, so the bucket claimed a dish it didn't sell. The buckets are `Drinks`, `Fast food`, `Main course` and so on now, and a test asserts none is named after a dish.

Only *spelling* corrections come back in the response as `{typed: used}` — synonyms widen the search silently and on purpose, because telling someone *"dimsum dikha rahe hain momos ke liye"* when they spelled momos perfectly is noise, not transparency. A correction is reported under the food's canonical name, so landing on "chaumin" is shown as "chowmein". The app says so on screen — *"chowmein dikha rahe hain "chawmin" ke liye"*. A search that quietly looks for a different word than the one you typed is how people stop trusting results they can't explain.

**Semantic search** uses the item embeddings (`embeddings.similar_items`) to bridge words that share no letters at all — "dumpling" to a menu that only says Momos. It is skipped entirely when the embedding backend has fallen back to hashing: those vectors encode literal token overlap and nothing else, so cosine similarity between them is noise. In practice it scored "tea" against a vendor called "Raju Momos" above the match threshold. A confident wrong answer is worse than no semantic layer, so `embeddings.semantic_ready()` gates it.

The owner panel says plainly whether it's running: **Semantic search ON/OFF** in AI Settings, from `semantic_ready` on `/api/admin/embeddings/status`. `enabled` was always true even on the hashing fallback, which made it a claim nobody could check.

> The local model (`BAAI/bge-small-en-v1.5`, via fastembed) downloads on first use. Until it does — or if the download is blocked — semantic search stays off and search runs on names, spelling correction and synonyms, which covers most of the same ground. **Setting `GEMINI_API_KEY` and picking the Gemini embedding model turns it on immediately, with no download.**

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

### API

Still prefixed `/api/food/*`. Renaming it (and `app/food.py`, and `Shop.food_kind`) to something family-neutral is a mechanical pass deliberately left for later, so that widening the domain and moving every reference didn't land in one diff.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/food/near?lat&long&q&kind&family&open_now&limit` | The home screen. No `q` = everything nearby, nothing excluded for distance — sorted nearest-first instead. `family` narrows to `food`/`goods`/`services`. Returns `corrections` alongside `vendors` |
| `POST` | `/api/food/add` | Photo add (multipart: repeated `photos` — or a single `photo` — plus `lat`, `long`, optional `name`/`kind`/`address`/`device_id`/`day_of_week`/`start_time`/`end_time`) |
| `POST` | `/api/food/survey` | Survey add: one shop plus everything it sells and repairs in a single request. `shop_id` adds to an existing shop; duplicate items are skipped |
| `GET` | `/api/food/geocode/reverse?lat&long` | Coordinates → address, so the add screens can show and correct it before saving |
| `GET` | `/api/food/{shop_id}?lat&long` | One vendor card |
| `POST` | `/api/food/{shop_id}/seen` | `{"yes": false, "reason": "closed_today"}` — the freshness vote |
| `POST` | `/api/food/{shop_id}/report` | `{"reason": "fake", "device_id": "…"}` — flag a bad listing |
| `POST` | `/api/food/{shop_id}/items` | Add one thing by hand — `{"name", "category", "price", "kind"}`; `kind` is inferred from the name when blank |
| `GET` | `/api/food/kinds` | Vendor kinds **and families**, popular chips, categories, and both reason lists |
| `GET` | `/api/admin/vendors?q&kind&hidden` | Owner panel's vendor list |
| `PATCH` | `/api/admin/shops/{id}` | Rename / fix a listing |
| `DELETE` | `/api/admin/shops/{id}` | Delete a listing, menu and rounds |
| `GET` | `/api/admin/reports?hidden_only` | Owner review queue for flagged listings |
| `POST` | `/api/admin/shops/{id}/visibility` | Hide or restore a listing (restoring clears its reports) |
| `POST` | `/api/admin/data/clear` | Wipe all thele, dishes, rounds and reports (AI settings kept) |
| `POST` | `/api/admin/data/sample` | Generate demo thele around `{lat, long, count, replace}` |

## Pages

Four screens, and the owner panel's dashboard links to all of them. The food app carries a small **Owner panel** link in its header.

| Path | Where | What it is |
|---|---|---|
| `/` | front end | The app — the customer-facing product |
| `/survey.html` | front end | Village survey: map shops on foot, offline-tolerant |
| `/admin.html` | front end | Owner panel: Dashboard, Jagah, Reports, AI Settings |
| `/docs` | backend | Interactive API docs — deliberately not linked from the panel (it's a developer surface) |

The front-end host also rewrites `/admin` → `/admin.html`, but nothing links to it that way: a plain file server has no rewrites, so a link that depends on one works in production and 404s in dev.

The owner panel has exactly one management surface — the **Vendors** tab: every listing with its kind, menu size, round count, how many people confirmed it, and whether it's live, reported or hidden. Rename fixes the common case (a misread signboard) in one prompt; delete takes the menu and rounds with it. It replaced a generic shops table that showed shopkeeper names and phone numbers — columns this product no longer has, since nobody registers their own listing and numbers are never captured.

**Sample thele** are on the dashboard next to Clear: 50 generated listings with menus, prices, rounds and a spread of freshness, placed around **the browser's current location** (the app's default location if it won't say). Both parts matter — sample data a thousand kilometres away answers nothing about "paas me kya mil raha hai", and a dataset where every row looks alike can't show whether the ranking works. Some carts are out right now and some come on Thursdays, some were confirmed today and some three weeks ago, a couple are already reported, and some boards hide their rates. Generator lives in `app/sample_food.py`; `{"replace": true}` wipes first.

**Clearing data** is on the dashboard under a red *Clear all data* card (two confirms). It deletes shops, items, rounds and reports; AI model choices and the retention flag survive, because someone clearing test data wants an empty map, not to redo the setup that made the map work. Deletion goes through children explicitly: a bulk `DELETE` never loads the rows, so SQLAlchemy's cascade doesn't run, and SQLite doesn't enforce foreign keys by default — which used to leave orphaned rounds and reports behind.

Vendor kinds, families and item categories all live in `app/food.py` — see the [Families](#families) table above.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(empty)_ | Claude Vision for reading vendor boards. |
| `GROQ_API_KEY` | _(empty)_ | Groq Vision (e.g. Llama 4 Scout). |
| `GEMINI_API_KEY` | _(empty)_ | Gemini Vision (e.g. 2.5 Flash). |
| `MYNA_DATABASE_URL` | _(falls back to `DATABASE_URL`, then SQLite)_ | Postgres URL. Checked first; `DATABASE_URL` (auto-set by Render/Heroku) is the fallback. |
| `DATABASE_URL` | `sqlite:///./myna.db` | Postgres URL supplied by hosting platform, or a manual override. |
| `EXA_API_KEY` | _(empty)_ | Web search grounding (`app/web_search.py`) — for trending / weather suggestions later. Falls back to keyless DuckDuckGo. |
| `MYNA_TIMEZONE` | `Asia/Kolkata` | Timezone that thela round timings are read in. |
| `CLOUDINARY_CLOUD_NAME` | _(empty)_ | Photo storage. All three needed; without them kept photos fall back to local disk. |
| `CLOUDINARY_API_KEY` | _(empty)_ | ↑ |
| `CLOUDINARY_API_SECRET` | _(empty)_ | ↑ |
| `UPLOAD_DIR` | `./uploads` | Where the local-disk fallback writes. |

> **Without any API key the app still runs** — the photo read just fails, and you type the vendor's name yourself on the review screen. Set any provider key to turn the one-photo flow on.

## Project structure

```
app/
  main.py            FastAPI app + lightweight migrations. JSON only — no pages
  config.py          Env-driven settings
  database.py        SQLAlchemy engine/session + DB-stored settings
  models.py          shops (vendors) + stops (rounds) + items (stock/capability)
                     + reports
  schemas.py         Pydantic request/response models
  food.py            Vendor families/kinds, item categories, product-vs-service,
                     synonyms, Hinglish labels, vote reasons
  geo.py             Haversine distance + Nominatim reverse geocode
  schedule.py        Thela rounds: "when is he here" + human timings
  ai.py              Multi-provider vision/text (Anthropic / Groq / Gemini)
                     + read_food_board / read_food_boards / merge_boards
  embeddings.py      Local (or Gemini) embeddings for menu items
  vision_check.py    Generates a test board and checks a model really reads it
  web_search.py      Exa/DuckDuckGo grounding — unused today, kept for planned
                     trending + weather-based suggestions (tested, not dead)
  images.py          Downscaling: one size for the model, a smaller one to store
  storage.py         Temp files for the vision read; Cloudinary for kept photos
  routers/
    food.py          Photo add, survey add, near, seen votes, reports, items,
                     geocode, reference data
    admin.py         Stats, vendors, review queue, AI settings, clear-all
  static/            The front end — its own deploy, never served by the API
    index.html       The app
    survey.html      Village survey: map shops on foot, queues when offline
    admin.html       Owner panel
    config.js        Backend origin (overwritten by the static site's build)
uploads/             Local-disk photo fallback, dev only (gitignored)
run.sh               Creates venv, then runs the API and the UI
test_smoke.py        End-to-end smoke test — no live server needed
```

## Deploy to Render (free plan)

One-click deploy using the included `render.yaml` blueprint:

1. Push this repo to GitHub, then in Render: **New → Blueprint** → select the repo.
2. Render creates the web service and a **free PostgreSQL DB** automatically.
3. After deploy, open the **`myna`** service's **Environment** tab and add your keys (`ANTHROPIC_API_KEY` / `GROQ_API_KEY` / `GEMINI_API_KEY`, plus the `CLOUDINARY_*` trio if you want photos kept) — all are marked `sync: false` in the blueprint, so Render never sets them for you.
4. Open `https://<frontend>.onrender.com/admin.html` to pick the default model, and use **AI Settings → Test with a sample photo** to prove it can actually read one. The panel is part of the front end; the backend URL has no pages on it.

**Two services, by design.** The backend is a plain JSON API with no idea what a client looks like — nothing is server-rendered, and the web app, a future mobile app and anything else all reach the same `/api/*` endpoints over CORS. The static front end also keeps the browser out from behind the free backend's ~30 s cold start.

| | `myna` (backend) | `myna-app` (front end) |
|---|---|---|
| The pages | ❌ 404 — it serves JSON, `/` included | ✅ |
| `/api/*`, `/docs` | ✅ | ❌ 404 — a static host has neither |

The backend used to serve the pages too, as a local-dev convenience. It cost more than it saved: the same app answered at two addresses with different configuration, so testing the wrong one passed silently — which is exactly how "search purana hi dikh raha hai" survived a working deploy. One front door.

Splitting the deploy is fine. Letting the two halves **drift apart** is what actually broke, and the blueprint guards each way now:

- **Version drift** — the front end served older HTML than the backend was running, so the app looked un-deployed when the deploy had in fact succeeded. `autoDeploy: true` is explicit on both services: one push, both, same commit.
- **Address drift** — the front end doesn't store the backend's URL at all. Render resolves it from the backend service (`fromService: {name: myna, property: host}`), so it can't go stale and it survives the backend being recreated under a new name — which is exactly what a fresh blueprint apply does. It used to be typed in twice, and the first re-create would have pointed the front end at a dead host. Belt and braces: if the address is ever wrong anyway, the app probes `/api/food/health` on failure and names what it's calling, rather than telling the user to check their connection.
- **`/docs` 404 on the front end** — expected, not a bug. It's a developer surface; open it on the backend URL. The owner panel doesn't link to it.

Two things that were genuine code bugs can no longer fail: the pages read `window.MYNA_API_BASE` instead of assuming same-origin (they hardcoded an empty base, which broke the app on the static host completely), and the web app is named `index.html` so a static host has a root document at all.

> **Free-tier notes:**
> - **Set the Cloudinary keys if you turn photo retention on.** Without them a kept photo is written to the instance's local disk, which Render wipes on every deploy — the listing survives, the picture 404s. The owner panel names the live backend next to the toggle so this isn't invisible. Photos the AI reads are temp files either way and are always deleted.
> - The free Postgres DB expires after **90 days** — upgrade to a paid tier to keep it.
> - Service **sleeps after ~15 min idle**; first request takes ~30 s to wake up.

## Planned, not built

`app/web_search.py` is in the tree with nothing calling it yet. It's kept deliberately for two features the model can't do from its own knowledge:

- **Trending** — what people are actually eating this week, so the home screen leads with that instead of a fixed chip list.
- **Weather-based suggestions** — barish me pakode aur chai, garmi me shikanji aur lassi.

An uncalled module is one that rots silently, so its result-shaping is covered in `test_smoke.py` against faked Exa and DuckDuckGo backends — no network, no API key needed. Both features are still unbuilt; the plumbing is just ready for them.

## One word: jagah

Everything a listing can be — a moving cart, a chai tapri, a dhaba, a restaurant — is a **jagah** in the UI. It was "thela" for a while, which was wrong in two ways at once: a dhaba is not a cart, and "Thela" was simultaneously the name of one specific kind, so the word meant two things on the same screen. "Jagah" is true of all of them and collides with nothing, which frees *thela* to mean just a cart again.

The code and API say `vendor` throughout — same concept, English word, and `shop_id` survives in the schema because renaming a primary key is a migration with no user-visible payoff.

## Known limitations

- **The board read is untested against real photos.** Everything here rests on the AI getting a name and a menu off a real signboard — blurry, angled, at night, spelled "chowmin". Without an API key only the failure paths have been exercised. This is the first thing to find out.
- No claim flow — a vendor can't take over their own listing, which is what should unlock the phone-number field.
- `device_id` is an anonymous localStorage string. It stops accidental double-voting and one-person report floods, but clearing storage mints a new id, so it isn't real abuse resistance — that needs a server-side signal.
- "Aaj band hai" is a single flag, not a history, so a vendor shut every Monday looks the same as one shut once. Repeated closures on the same weekday should eventually become a schedule.
- Reports aren't weighted by reporter — three throwaway devices hide a listing as effectively as three real ones.
- Semantic search needs the local embedding model to download on first use. Until then search is substring plus spelling correction, which handles typos but not synonyms.
- Rounds can only be set when a listing is added; there's no edit-a-round screen.
- Nominatim is rate-limited (~1 req/s) — fine at pilot volume.

## History

Myna started as a general hyperlocal product finder: shopkeepers listed their own stock, customers searched for any product, and a dish could be expanded into a kirana shopping list. That version is gone as of the food pivot — a kirana's 500 items can't come off one photo, and vendors never keep their own listings current. Both problems disappear on street food, where the board *is* the menu and any passer-by can add a cart. See the git history for the old app.
