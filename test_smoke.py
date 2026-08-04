"""End-to-end smoke test using FastAPI TestClient (no live server needed)."""
import io
import os

# Prevent .env from being loaded during tests — we don't want real keys.
os.environ["MYNA_SKIP_DOTENV"] = "1"

# Use a throwaway test DB so repeated runs don't accumulate data.
_test_db = "test_myna_smoke.db"
if os.path.exists(_test_db):
    os.remove(_test_db)
os.environ["DATABASE_URL"] = f"sqlite:///./{_test_db}"

# Clear any real API keys from the environment / .env — tests must not call real APIs.
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("GROQ_API_KEY", None)
os.environ.pop("GEMINI_API_KEY", None)

from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# 1. Pages
# ---------------------------------------------------------------------------
assert client.get("/").status_code == 200
assert client.get("/admin").status_code == 200
# The general-purpose product search and the shopkeeper self-onboarding page
# were removed with the food pivot — they must not answer any more.
assert client.get("/classic").status_code == 404
assert client.get("/shopkeeper").status_code == 404
# Their APIs went too: no shop CRUD, no item CRUD, no agentic search, no CSV.
for gone in ("/api/search", "/api/search/shops", "/api/search/one-tap",
             "/api/search/dishes", "/api/catalog", "/api/admin/items",
             "/api/admin/shops", "/api/admin/import/template"):
    assert client.get(gone).status_code == 404, gone
# The static catch-all answers unknown GETs, so a removed POST route surfaces
# as 405 rather than 404 — either way, nothing handles it.
assert client.post("/api/shops", json={"name": "x", "lat": 1.0, "long": 1.0}).status_code in (404, 405)
print("PASS pages load, removed pages and APIs are gone")

# ---------------------------------------------------------------------------
# 2. Rounds: schedule maths for a thela that moves
# ---------------------------------------------------------------------------
from app import schedule as _sched

# Against a frozen clock (a Wednesday, 11:00).
_wed = datetime(2026, 8, 5, 11, 0, tzinfo=_sched.tz())
assert _wed.weekday() == 2
live = _sched.status(2, "10:00", "12:00", _wed)          # Wednesday 10-12, now 11:00
assert live["status"] == "here_now" and live["rank"] == _sched.AVAILABLE_NOW
assert "12 PM" in live["status_text"]
soon = _sched.status(2, "11:30", "13:00", _wed)
assert soon["status"] == "today" and soon["rank"] == _sched.LATER_TODAY
assert "30 min" in soon["status_text"]
later = _sched.status(2, "17:00", "19:00", _wed)
assert later["rank"] == _sched.LATER_TODAY and later["status_text"].startswith("Today")
weekly = _sched.status(4, "10:00", "12:00", _wed)        # every Friday
assert weekly["rank"] == _sched.ANOTHER_DAY and weekly["status_text"].startswith("Fri")
tomorrow = _sched.status(3, "10:00", "12:00", _wed)
assert tomorrow["status_text"].startswith("Tomorrow")
daily_done = _sched.status(_sched.EVERY_DAY, "07:00", "09:00", _wed)   # already over today
assert daily_done["status_text"].startswith("Tomorrow")
assert _sched.describe(1, "10:00", "12:00") == "Every Tuesday \u00b7 10 AM \u2013 12 PM"
assert _sched.describe(-1, "09:30", "13:45") == "Every day \u00b7 9:30 AM \u2013 1:45 PM"
assert _sched.parse_hhmm("25:00") is None and _sched.parse_hhmm("") is None
print("PASS schedule status/format for rounds")

# ---------------------------------------------------------------------------
# 3. AI plumbing: vision tagging, the self-test, settings, embeddings
# ---------------------------------------------------------------------------
from app import ai as _ai

# Picking a text-only model for OCR used to break every photo silently, so
# models are tagged and the panel can prove a model really reads images.
assert _ai.supports_vision("claude-sonnet-4-20250514") is True
assert _ai.supports_vision("gemini-2.5-flash") is True
assert _ai.supports_vision("meta-llama/llama-4-scout-17b-16e-instruct") is True
assert _ai.supports_vision("openai/gpt-oss-120b") is False
assert _ai.supports_vision("llama-3.3-70b-versatile") is False
assert _ai.supports_vision("whatever", {"capabilities": {"vision": True}}) is True
result = client.post("/api/admin/llm/vision-test", json={"model": ""}).json()
assert result["status"] == "unconfigured", result   # no API key in tests
print("PASS vision capability tagging + self-test endpoint")

# No keys configured in tests, so providers list empty but the endpoints hold.
assert client.get("/api/admin/llm/providers").json()["configured_providers"] == []
assert client.get("/api/admin/llm/models").json()["models"] == []
# The local embedding backend is always available, with or without API keys.
emb = client.get("/api/admin/llm/embedding-models").json()["models"]
assert any(m["provider"] == "local" for m in emb), emb
assert client.get("/api/admin/embeddings/status").status_code == 200
print("PASS admin LLM + embedding endpoints without any API key")

settings = client.get("/api/admin/settings").json()
assert settings["retain_uploaded_images"] is False       # off by default
res = client.patch("/api/admin/settings", json={
    "default_vision_model": "anthropic/claude-sonnet-4-20250514",
    "default_search_model": "gemini/gemini-2.5-flash",
    "default_embedding_model": "local/BAAI/bge-small-en-v1.5",
})
assert res.status_code == 200, res.text
after = client.get("/api/admin/settings").json()
assert after["default_vision_model"] == "anthropic/claude-sonnet-4-20250514"
assert after["default_search_model"] == "gemini/gemini-2.5-flash"
assert after["default_embedding_model"] == "local/BAAI/bge-small-en-v1.5"
print("PASS admin settings round-trip")

# Vision replies come back in three shapes depending on the model; all three
# still feed the board parser's fallback path.
assert [i["name"] for i in _ai._parse_items(
    '[{"name":"Tata Salt 1kg","category":"Grocery"}]')] == ["Tata Salt 1kg"]
assert [i["name"] for i in _ai._parse_items(
    '```json\n[{"name":"Parle-G","category":"Snacks"}]\n```')] == ["Parle-G"]
assert [i["name"] for i in _ai._parse_items(
    "- Amul Milk | Dairy\n- Britannia Bread | Bakery")] == ["Amul Milk", "Britannia Bread"]
assert len(_ai._parse_items('[{"name":"Salt"},{"name":"salt"}]')) == 1     # deduped
print("PASS vision reply parsing (json, fenced json, bullet lines, dedupe)")



# ---------------------------------------------------------------------------
# 3b. Web search grounding — kept for trending / weather suggestions
# ---------------------------------------------------------------------------
# Nothing calls this yet, which is exactly why it's tested: an unused module
# with no coverage is one that silently stops working. Both backends are faked,
# so this needs no network and no API key.
from app import web_search as _ws


class _FakeResp:
    def __init__(self, payload): self._payload = payload
    def raise_for_status(self): pass
    def json(self): return self._payload


class _FakeDDGS:
    results = []
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def text(self, query, max_results=5): return self.results[:max_results]


# Exa path: response shaped into {title, snippet, url}, whitespace kept as-is.
_ws.EXA_API_KEY = "test-key"
_orig_post = _ws.httpx.post
_ws.httpx.post = lambda *a, **k: _FakeResp({"results": [
    {"title": "Monsoon street food", "text": "  pakode aur chai  ", "url": "http://x/1"},
    {"title": "No text field", "url": "http://x/2"},
]})
out = _ws.search("what is trending")
assert [r["title"] for r in out] == ["Monsoon street food", "No text field"]
assert out[0]["snippet"] == "pakode aur chai"      # stripped
assert out[1]["snippet"] == ""                     # missing field, not a crash

# A prompt block collapses whitespace, truncates, and drops empty snippets.
_ws.httpx.post = lambda *a, **k: _FakeResp({"results": [
    {"title": "t", "text": "garmi\n\n  me   lassi", "url": "u"},
    {"title": "empty", "text": "   ", "url": "u"},
    {"title": "long", "text": "x" * 900, "url": "u"},
]})
block_text = _ws.context_block("weather food")
lines = block_text.split("\n")
assert lines[0] == "- garmi me lassi", lines[0]     # whitespace collapsed
assert len(lines) == 2                              # blank snippet dropped
assert len(lines[1]) == 2 + _ws._SNIPPET_CHARS      # truncated

# Exa failing falls through to DuckDuckGo rather than surfacing an error.
_ws.httpx.post = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("exa down"))
_FakeDDGS.results = [{"title": "ddg hit", "body": "momos", "href": "http://d/1"}]
_ws_ddgs_module = type("m", (), {"DDGS": _FakeDDGS})
import sys as _sys
_sys.modules["ddgs"] = _ws_ddgs_module
assert _ws.search("anything") == [
    {"title": "ddg hit", "snippet": "momos", "url": "http://d/1"}]

# Both backends dead: [] and no exception — callers treat this as optional.
_FakeDDGS.results = []
assert _ws.search("anything") == []
assert _ws.context_block("anything") == ""
# No key at all skips Exa entirely.
_ws.EXA_API_KEY = ""
assert _ws.search("anything") == []
_ws.httpx.post = _orig_post
del _sys.modules["ddgs"]
print("PASS web search grounding (exa, ddg fallback, prompt block, failure)")


# ---------------------------------------------------------------------------
# 4. Food app: one-photo add, "paas me kya hai", freshness votes
# ---------------------------------------------------------------------------
from app import ai as _ai, food as _food

# 47a. Vocabulary
assert _food.normalise_kind("Chinese") == "chinese"
assert _food.normalise_kind("momos") == "chinese"      # inferred from a hint
assert _food.normalise_kind("") == "other"
assert _food.suggest_category("Veg Chowmein") == "Chinese"
assert _food.suggest_category("Gulab Jamun") == "Sweets"
assert _food.suggest_category("Chilli Potato") == "Chinese"
assert _food.normalise_category("nonsense", "Masala Chai") == "Drinks"
# Every chip the home screen offers must be a dish the vocabulary actually
# knows, not one that silently lands on the default category. "Golgappe" used
# to miss because only "golgappa" was listed — the app's own top chip.
_unknown = [
    chip for chip in _food.POPULAR
    if not any(hint in chip.lower()
               for hints in _food.CATEGORIES.values() for hint in hints)
]
assert not _unknown, f"popular chips no category knows: {_unknown}"
assert _food.suggest_category("Golgappe") == "Chaat & street"
assert _food.normalise_kind("golgappe") == "chaat"
print("PASS food vocabulary")

# 47a-2. Search: splitting a query, spelling, and word boundaries.
assert _food.split_query("momos aur chawmin") == ["momos", "chawmin"]
assert _food.split_query("chole bhature ya pav bhaji") == ["chole bhature", "pav bhaji"]
assert _food.split_query("chai chai") == ["chai"]            # repeats folded
assert _food.split_query("  ") == []
assert "aur" not in _food.split_query("momos aur chai")      # joiners aren't dishes

# Which exact spelling a typo lands on is edit-distance trivia once synonyms
# are in the vocabulary too ("chaumin", "momoz" are known words now). What has
# to hold is that it lands on a word meaning the dish that was wanted.
def _means(typed, dish):
    fixed = _food.correct_term(typed)
    return fixed == dish or dish in _food.synonyms_of(fixed)

assert _means("chawmin", "chowmein")
assert _means("momoz", "momos")
assert _food.correct_term("momos") == "momos"                # already right
assert _food.correct_term("chai") == "chai"                  # never becomes "chaat"
assert _food.correct_term("zzzznotafood") == "zzzznotafood"  # no wild guess
assert _food.correct_term("momo") == "momo"                  # prefix, not a typo
# Menu words found nearby widen the target, so a dish the built-in list never
# heard of is still reachable through a misspelling.
_menu_fixed = _food.correct_term("shwrma", _food.vocabulary({"shawarma"}))
assert _menu_fixed == "shawarma" or "shawarma" in _food.synonyms_of(_menu_fixed), _menu_fixed
print("PASS query splitting + spelling correction")

from app.routers.food import term_in
# The bug this exists for: "tea" sits inside "Steam Momos", so a plain
# substring check returned a momos cart for a tea search.
assert term_in("tea", "raju momos steam momos") is False
assert term_in("chai", "bansal chai tapri masala chai") is True
assert term_in("momo", "raju momos") is True                 # prefix still matches
assert term_in("samosa", "garam samosas") is True
assert term_in("", "anything") is False
print("PASS word-aware matching")

# A category is a bucket, not a dish. Naming one "Chai & drinks" made every
# juice stall match a search for "chai", because search reads the category too.
for _bucket in _food.CATEGORY_NAMES:
    _clash = [d for d in ("chai", "roll", "tandoor", "momo", "dosa", "jalebi")
              if d in _bucket.lower()]
    assert not _clash, f"category {_bucket!r} is named after dish(es) {_clash}"
print("PASS category names don't claim a dish")

# 47a-3. Synonyms — the same food under a different name. This is what carries
# meaning-based search when no embedding model is available, and for a
# vocabulary this small it's more reliable than one anyway.
assert "momos" in _food.synonyms_of("dumpling")
assert "chowmein" in _food.synonyms_of("noodles")
assert "golgappe" in _food.synonyms_of("puchka")
assert "golgappe" in _food.synonyms_of("gupchup")
assert "chai" in _food.synonyms_of("tea")
assert _food.synonyms_of("zzzznotafood") == set()
# Matching is prefix-friendly, which makes short synonyms landmines: "cha" for
# chai matched every *Chaat* stall, "ras" for juice matched Rasgulla. Anything
# a synonym expands to must not be a prefix of a dish in another group.
_groups = {}
for _i, _g in enumerate(_food.SYNONYM_GROUPS):
    for _w in _g:
        _groups.setdefault(_w, set()).add(_i)
_collisions = [
    (w, other) for w, idx in _groups.items() if len(w) >= _food.MIN_SYNONYM_LENGTH
    for other, oidx in _groups.items()
    if not (idx & oidx) and other != w and other.startswith(w)
]
assert not _collisions, f"synonym prefix collisions: {_collisions}"
assert all(len(w) >= _food.MIN_SYNONYM_LENGTH
           for word in _groups for w in _food.synonyms_of(word))
print("PASS synonyms (cross-name search, no short-word landmines)")

# 47b. Board parsing — the object shape, a fenced reply, and the array fallback.
board = _ai._parse_board(
    '{"name": "Sharma Chinese Corner", "kind": "chinese", "items": '
    '[{"name": "Chowmein", "price": "₹40", "category": "Chinese"},'
    ' {"name": "Veg Momos", "price": 50, "category": "Chinese"},'
    ' {"name": "Chowmein", "price": 40}]}'
)
assert board["name"] == "Sharma Chinese Corner" and board["kind"] == "chinese"
assert len(board["items"]) == 2, board["items"]          # duplicate folded
assert board["items"][0]["price"] == 40.0                # "₹40" parsed
assert board["items"][1]["name"] == "Veg Momos"
fenced = _ai._parse_board('```json\n{"name":"Tapri","kind":"chai","items":[]}\n```')
assert fenced["name"] == "Tapri" and fenced["kind"] == "chai"
# No object at all: the menu still survives via the array parser, and the kind
# is inferred from the dishes rather than lost.
loose = _ai._parse_board('[{"name": "Golgappe"}, {"name": "Aloo Tikki"}]')
assert [i["name"] for i in loose["items"]] == ["Golgappe", "Aloo Tikki"]
assert loose["kind"] == "chaat", loose["kind"]
assert _ai._parse_price("Rs 60/-") == 60.0 and _ai._parse_price("free") == 0.0
assert _ai._parse_price(-5) == 0.0
print("PASS board parsing")

# 47c. One-photo add. No API key is configured in tests, so the vision read
# fails — the flow must still list the vendor from the typed name rather than
# dropping it.
food_img = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
res = client.post("/api/food/add", data={
    "lat": 19.0760, "long": 72.8777, "name": "Sharma Chinese Corner",
    "kind": "chinese", "address": "Link Road, Andheri", "device_id": "dev-test-1",
}, files={"photo": ("board.jpg", food_img, "image/jpeg")})
assert res.status_code == 200, res.text
added = res.json()
assert added["created"] is True
vendor = added["vendor"]
assert vendor["kind_label"] == "Chinese thela" and vendor["food_kind"] == "chinese"
assert vendor["seen_yes"] == 1 and vendor["seen_text"] == "Aaj dekha gaya"
assert vendor["trust"] == "fresh"
assert vendor["phone"] == ""            # add flow never captures a vendor's number
food_id = vendor["shop_id"]
print(f"PASS one-photo add id={food_id}")

# 47c-2. Several photos of one vendor merge into one listing: the first photo's
# name wins, dishes union, and a price found in a close-up fills in for the
# same dish photographed without one.
wide = {"name": "Raju Chinese Corner", "kind": "chinese",
        "items": [{"name": "Chowmein", "price": 0.0, "category": "Chinese"},
                  {"name": "Momos", "price": 0.0, "category": "Chinese"}]}
close = {"name": "", "kind": "other",
         "items": [{"name": "chowmein", "price": 40.0, "category": "Chinese"},
                   {"name": "Spring Roll", "price": 60.0, "category": "Chinese"}]}
tawa = {"name": "Momos wala", "kind": "chaat", "items": []}
merged = _ai.merge_boards([wide, close, tawa])
assert merged["name"] == "Raju Chinese Corner"       # first non-empty wins
assert merged["kind"] == "chinese"                   # majority of real kinds
names = [i["name"] for i in merged["items"]]
assert names == ["Chowmein", "Momos", "Spring Roll"], names   # union, first spelling
prices = {i["name"]: i["price"] for i in merged["items"]}
assert prices["Chowmein"] == 40.0                    # close-up filled the price in
assert prices["Spring Roll"] == 60.0
# A photo that read as nothing at all doesn't wipe what the others found.
assert _ai.merge_boards([wide, {"name": "", "kind": "other", "items": []}])["items"]
# No real kind anywhere: infer it from the merged menu rather than give up.
assert _ai.merge_boards([{"name": "X", "kind": "other",
                          "items": [{"name": "Golgappe", "price": 0, "category": ""}]}
                         ])["kind"] == "chaat"
print("PASS multi-photo merge")

# 47c-3. The endpoint takes repeated `photos`, still takes a single `photo`,
# and refuses a request with neither.
def _img():
    return io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 60)

res = client.post("/api/food/add", data={
    "lat": 19.0759, "long": 72.8776, "name": "Teen Photo Wala", "kind": "chinese",
}, files=[("photos", ("a.jpg", _img(), "image/jpeg")),
          ("photos", ("b.jpg", _img(), "image/jpeg")),
          ("photos", ("c.jpg", _img(), "image/jpeg"))])
assert res.status_code == 200, res.text
assert res.json()["created"] is True and res.json()["photo_count"] == 3
multi_id = res.json()["vendor"]["shop_id"]
# Over the cap, only MAX_PHOTOS are read — this bounds both cost and wait.
res = client.post("/api/food/add", data={
    "lat": 19.0759, "long": 72.8776, "name": "Bahut Photo Wala",
}, files=[("photos", (f"{i}.jpg", _img(), "image/jpeg")) for i in range(9)])
assert res.json()["photo_count"] == 5, res.json()["photo_count"]
assert client.post("/api/food/add", data={
    "lat": 19.0759, "long": 72.8776, "name": "No Photo"}).status_code == 422
print("PASS multi-photo add endpoint (repeated field, cap, single-photo alias)")

# 47d. Nothing readable and nothing typed → no listing, and a Hinglish reason.
res = client.post("/api/food/add", data={"lat": 19.0760, "long": 72.8777}, files={
    "photo": ("blank.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")})
assert res.json()["created"] is False and res.json()["error"]
print("PASS unreadable photo is refused, not half-saved")

# 47e. Menu items added by hand get a category derived from the dish name.
res = client.post(f"/api/food/{food_id}/items", json={"name": "Veg Momos", "price": 50})
assert res.status_code == 200, res.text
assert res.json()["category"] == "Chinese" and res.json()["price"] == 50.0
client.post(f"/api/food/{food_id}/items", json={"name": "Masala Chai", "price": 10})
print("PASS manual menu item")

# 47f. Browse + search. A dish query matches the menu; a name query matches the
# board; and something nobody sells returns nothing rather than everything.
near = client.get("/api/food/near", params={"lat": 19.0760, "long": 72.8777}).json()
assert near["count"] >= 1
assert any(v["shop_id"] == food_id for v in near["vendors"])
hit = client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "q": "momos"}).json()
assert [v["shop_id"] for v in hit["vendors"]] == [food_id], hit
assert hit["vendors"][0]["matched"] == ["momos"]
assert any(m["name"] == "Veg Momos" and m["price"] == 50.0
           for m in hit["vendors"][0]["menu"])
by_name = client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "q": "sharma"}).json()
assert any(v["shop_id"] == food_id for v in by_name["vendors"])
miss = client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "q": "zzzznotadish"}).json()
assert miss["count"] == 0
# Far away is out of range, and the kind filter is exclusive.
far = client.get("/api/food/near", params={"lat": 28.6139, "long": 77.2090}).json()
assert all(v["shop_id"] != food_id for v in far["vendors"])
kinds = client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "kind": "sweets"}).json()
assert all(v["shop_id"] != food_id for v in kinds["vendors"])
print("PASS near: browse, dish search, name search, radius, kind filter")

# 4f-2. Two dishes, two vendors — each returned for its own word, and a typo
# on one of them doesn't cost you the other.
res = client.post("/api/food/add", data={
    "lat": 19.0760, "long": 72.8777, "name": "Chowmein Corner", "kind": "chinese",
}, files={"photo": ("cm.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")})
cm_id = res.json()["vendor"]["shop_id"]
client.post(f"/api/food/{cm_id}/items", json={"name": "Veg Chowmein", "price": 40})

both = client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "q": "momos aur chawmin"}).json()
by_id = {v["shop_id"]: v["matched"] for v in both["vendors"]}
assert food_id in by_id and cm_id in by_id, by_id
assert by_id[food_id] == ["momos"]        # the momos cart, for "momos"
assert by_id[cm_id] == ["chawmin"]        # the chowmein cart, for the typo
# Reported per original word, so the card can say why it's there.
assert client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "q": "momoz"}).json()["vendors"][0]["shop_id"] == food_id
# "tea" now legitimately reaches chai through synonyms, so the thing worth
# asserting is that every hit actually has it — not that there are none.
for _v in client.get("/api/food/near", params={
        "lat": 19.0760, "long": 72.8777, "q": "tea"}).json()["vendors"]:
    _text = (_v["name"] + " " + _v["kind_label"] + " "
             + " ".join(m["name"] for m in _v["menu"])).lower()
    assert "chai" in _text or "tea" in _text, _v["name"]
# And a word with no menu, synonym or spelling path still finds nothing.
assert client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "q": "zzzznotafood"}).json()["count"] == 0
# Corrections are reported, not applied silently — the UI says what it
# actually searched for, and highlights dishes on that spelling.
assert both["corrections"].get("chawmin") == "chowmein", both["corrections"]
assert client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "q": "momos"}).json()["corrections"] == {}
page = client.get("/").text
assert 'id="fixnote"' in page and "CORRECTIONS" in page
# A phone in dark mode used to ignore an explicit "light" choice: a media
# query can't be overridden by an attribute set later, so the override has to
# exist as its own rule. Both directions, and the same storage key as the
# owner panel so one choice covers both screens.
assert ':root[data-theme="dark"]' in page
assert ':root:not([data-theme="light"])' in page
assert 'myna_theme' in page and 'id="themeBtn"' in page
assert 'myna_theme' in client.get("/admin").text
# A dead or mis-set API base used to surface as "check your connection", which
# blamed the user for a deploy mistake and hid it from everyone. The client
# probes health so it can name the real problem.
assert client.get("/api/food/health").json()["ok"] is True
assert "failureMessage" in page and "/api/food/health" in page
assert "config.js" in page
# The API must stay usable by any client, not just these pages — a mobile app
# is the same JSON over the same CORS-open endpoints, with no HTML involved.
_probe = client.get("/api/food/near", params={"lat": 19.076, "long": 72.8777},
                    headers={"Origin": "capacitor://localhost"})
assert _probe.status_code == 200
assert _probe.headers.get("access-control-allow-origin") == "*"
print("PASS two dishes -> two vendors, each matched on its own word")

# 4f-3. Synonyms end to end: a word that shares no letters with the menu.
syn = client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "q": "dumpling"}).json()
assert food_id in [v["shop_id"] for v in syn["vendors"]], syn
assert client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "q": "noodles"}).json()["count"] >= 1
# "tea" must not reach a Chaat stall via the old three-letter "cha" synonym.
for v in client.get("/api/food/near", params={
        "lat": 19.0760, "long": 72.8777, "q": "tea"}).json()["vendors"]:
    assert "chaat" not in v["name"].lower(), v["name"]
print("PASS synonym search end to end")

# 4f-4. The semantic stage itself. The local model downloads on first use and
# may be unavailable, so the wiring is proven against a stub embedder instead —
# otherwise this whole path would be untested until it reached production.
from app import embeddings as _emb2
from app.routers.food import semantic_hits as _sem

_saved = (_emb2.semantic_ready, _emb2.similar_items)
try:
    _emb2.semantic_ready = lambda db=None: True
    _emb2.similar_items = lambda db, term, **kw: (
        [(1, food_id)] if term == "khaane" else []
    )
    hits = _sem(client.app.state.__dict__.get("_db") or None, [])   # empty terms short-circuit
    assert hits == {}
    from app.database import SessionLocal as _S2
    _d2 = _S2()
    try:
        assert _sem(_d2, ["khaane"]) == {"khaane": {food_id}}
        assert _sem(_d2, ["nothing"]) == {}
        # A broken backend must degrade to no semantic hits, never a 500.
        _emb2.similar_items = lambda db, term, **kw: (_ for _ in ()).throw(RuntimeError("boom"))
        assert _sem(_d2, ["khaane"]) == {}
    finally:
        _d2.close()
finally:
    _emb2.semantic_ready, _emb2.similar_items = _saved
print("PASS semantic stage wiring (stubbed model, failure degrades quietly)")

# Status says plainly whether meaning-based search is actually running —
# `enabled` was true even on the hashing fallback, which made it uncheckable.
st = client.get("/api/admin/embeddings/status").json()
assert "semantic_ready" in st and "active_model" in st
assert st["semantic_ready"] is _emb2.semantic_ready()
if not st["semantic_ready"]:
    assert "GEMINI_API_KEY" in st["reason"]
assert 'Semantic search ON' in client.get("/admin").text
print("PASS semantic readiness is reported, not assumed")

# 47g. Freshness votes. An unexplained "nahi mila" outvoting "haan hai" marks a
# listing doubtful, which sinks it below everything else nearby.
assert client.post(f"/api/food/{food_id}/seen", json={"yes": True}).json()["seen_yes"] == 2
for _ in range(4):
    client.post(f"/api/food/{food_id}/seen", json={"yes": False})
state = client.get(f"/api/food/{food_id}").json()
assert state["seen_no"] == 4 and state["trust"] == "doubtful"
assert client.post("/api/food/999999/seen", json={"yes": True}).status_code == 404
print("PASS freshness votes")

# 47h. "Aaj band hai" must NOT damage a listing — the whole point of asking
# why. A vendor closed for one holiday keeps its trust, stays in search, and
# only sinks for today.
res = client.post("/api/food/add", data={
    "lat": 19.0761, "long": 72.8778, "name": "Chhutti Wala Dhaba", "kind": "dhaba",
}, files={"photo": ("b.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")})
holiday_id = res.json()["vendor"]["shop_id"]
for _ in range(5):
    client.post(f"/api/food/{holiday_id}/seen", json={"yes": False, "reason": "closed_today"})
state = client.get(f"/api/food/{holiday_id}").json()
assert state["closed_today"] is True
assert state["trust"] == "fresh", state["trust"]     # five taps, zero damage
assert state["seen_text"] == "Aaj band bataya gaya"
assert state["seen_no"] == 0 and state["moved_count"] == 0
listing = client.get("/api/food/near", params={"lat": 19.0760, "long": 72.8777}).json()
ids = [v["shop_id"] for v in listing["vendors"]]
assert holiday_id in ids                             # still listed…
assert ids[-1] == holiday_id, ids                    # …just last for today
# Someone standing at the open shop overrides this morning's "band hai".
client.post(f"/api/food/{holiday_id}/seen", json={"yes": True})
assert client.get(f"/api/food/{holiday_id}").json()["closed_today"] is False
print("PASS 'aaj band hai' is a note, not a downvote")

# 47i. "Yahan se hat gaya" argues the spot is wrong; "hamesha ke liye band"
# weighs enough that two of them retire the listing from search entirely.
res = client.post("/api/food/add", data={
    "lat": 19.0762, "long": 72.8779, "name": "Bandh Ho Gaya Thela", "kind": "thela",
}, files={"photo": ("c.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")})
gone_id = res.json()["vendor"]["shop_id"]
client.post(f"/api/food/{gone_id}/seen", json={"yes": False, "reason": "moved"})
client.post(f"/api/food/{gone_id}/seen", json={"yes": False, "reason": "moved"})
state = client.get(f"/api/food/{gone_id}").json()
assert state["moved_count"] == 2 and state["trust"] == "doubtful"
for _ in range(2):
    client.post(f"/api/food/{gone_id}/seen", json={"yes": False, "reason": "shut_down"})
state = client.get(f"/api/food/{gone_id}").json()
assert state["shutdown_count"] == 2 and state["trust"] == "closed"
assert state["seen_text"] == "Log keh rahe hain ab lagta hi nahi"
gone_listing = client.get("/api/food/near", params={"lat": 19.0760, "long": 72.8777}).json()
assert all(v["shop_id"] != gone_id for v in gone_listing["vendors"])
# An unknown reason is accepted and weighed as a plain "nahi mila".
assert client.post(f"/api/food/{gone_id}/seen",
                   json={"yes": False, "reason": "kuch bhi"}).json()["seen_no"] == 1
print("PASS 'hat gaya' vs 'hamesha band' are weighed differently")

# 47j. Reports. One per device, three distinct devices hide the listing, and a
# hidden listing drops out of search without being deleted.
res = client.post("/api/food/add", data={
    "lat": 19.0763, "long": 72.8780, "name": "Fake Joke Entry", "kind": "chaat",
}, files={"photo": ("d.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")})
junk_id = res.json()["vendor"]["shop_id"]
first = client.post(f"/api/food/{junk_id}/report",
                    json={"reason": "joke", "device_id": "dev-a"}).json()
assert first["reported"] is True and first["report_count"] == 1 and first["hidden"] is False
# Same device again changes nothing — one person can't bury a competitor.
again = client.post(f"/api/food/{junk_id}/report",
                    json={"reason": "fake", "device_id": "dev-a"}).json()
assert again["reported"] is False and again["report_count"] == 1
client.post(f"/api/food/{junk_id}/report", json={"reason": "fake", "device_id": "dev-b"})
third = client.post(f"/api/food/{junk_id}/report",
                    json={"reason": "fake", "device_id": "dev-c", "note": "aisi dukaan nahi hai"}).json()
assert third["report_count"] == 3 and third["hidden"] is True
assert "review" in third["message"]
hidden_listing = client.get("/api/food/near", params={"lat": 19.0760, "long": 72.8777}).json()
assert all(v["shop_id"] != junk_id for v in hidden_listing["vendors"])
assert client.get(f"/api/food/{junk_id}").json()["hidden"] is True   # hidden, not deleted
assert client.post("/api/food/999999/report", json={"reason": "fake"}).status_code == 404
print("PASS reports hide a listing after 3 distinct devices")

# 47k. Owner review queue: see why, then restore — which must also clear the
# reports, or the next stray tap re-hides it.
queue = client.get("/api/admin/reports").json()
entry = next(r for r in queue if r["shop_id"] == junk_id)
assert entry["report_count"] == 3 and entry["hidden"] is True
assert entry["reasons"] == {"joke": 1, "fake": 2}, entry["reasons"]
assert "aisi dukaan nahi hai" in entry["notes"]
assert all(r["hidden"] for r in client.get("/api/admin/reports",
                                           params={"hidden_only": True}).json())
# The dashboard surfaces the queue, so it can't quietly pile up unreviewed.
stats = client.get("/api/admin/stats").json()
assert stats["reported_shops"] >= 1 and stats["hidden_shops"] >= 1
restored = client.post(f"/api/admin/shops/{junk_id}/visibility", json={"hidden": False}).json()
assert restored["hidden"] is False and restored["report_count"] == 0
back = client.get("/api/food/near", params={"lat": 19.0760, "long": 72.8777}).json()
assert any(v["shop_id"] == junk_id for v in back["vendors"])
assert all(r["shop_id"] != junk_id for r in client.get("/api/admin/reports").json())
assert client.get("/api/admin/stats").json()["hidden_shops"] == 0
# The owner panel has a screen for it, not just an endpoint.
panel = client.get("/admin").text
assert "id=\"tab-reports\"" in panel and "loadReports()" in panel
assert "/api/admin/reports" in panel and "visibility" in panel
assert "Restore &amp; clear reports" in panel and "reportPill" in panel
print("PASS owner review queue: inspect, restore, clear")

# 47k-2. Clear all data. The old CSV `replace` wipe deleted only shops and
# items, leaving rounds and reports behind as orphans nothing could reach.
res = client.post("/api/food/add", data={
    "lat": 19.0770, "long": 72.8790, "name": "Wipe Test Thela", "kind": "thela",
    "day_of_week": -1, "start_time": "09:00", "end_time": "21:00",
}, files={"photo": ("w.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")})
wipe_id = res.json()["vendor"]["shop_id"]
client.post(f"/api/food/{wipe_id}/items", json={"name": "Chai", "price": 10})
client.post(f"/api/food/{wipe_id}/report", json={"reason": "fake", "device_id": "dev-w"})
assert client.get(f"/api/food/{wipe_id}").json()["stops"]

from app import models as _models
from app.database import SessionLocal as _Session
cleared = client.post("/api/admin/data/clear").json()
assert cleared["cleared"] is True
assert cleared["shops"] >= 1 and cleared["items"] >= 1
assert cleared["stops"] >= 1 and cleared["reports"] >= 1
_db = _Session()
try:
    for _model in (_models.Shop, _models.Item, _models.ShopStop, _models.ShopReport):
        assert _db.query(_model).count() == 0, _model.__name__
finally:
    _db.close()
stats = client.get("/api/admin/stats").json()
assert stats["total_shops"] == 0 and stats["total_items"] == 0
assert client.get("/api/food/near", params={"lat": 19.076, "long": 72.878}).json()["count"] == 0
# Settings survive a clear — wiping test data shouldn't undo the AI setup.
client.patch("/api/admin/settings", json={"retain_uploaded_images": True})
client.post("/api/admin/data/clear")
assert client.get("/api/admin/settings").json()["retain_uploaded_images"] is True
client.patch("/api/admin/settings", json={"retain_uploaded_images": False})
print("PASS clear all data (children too, settings kept)")

# 4k-2b. Sample thele — the button next to Clear, for getting the map into a
# testable state.
from app import sample_food as _sf

built = _sf.build(19.0760, 72.8777, count=50, seed=7)
assert len(built) == 50
assert len({s.name for s in built}) == 50                  # no duplicate names
assert all(s.items for s in built)                         # every thela has a menu
assert all(_food.normalise_kind(s.food_kind) == s.food_kind for s in built)
# Placed within walking distance, not scattered across the country.
from app.geo import haversine_km as _hav
assert all(_hav(19.0760, 72.8777, s.lat, s.long) < 4 for s in built)
# Varied on the axes the UI actually ranks on, or it can't show anything.
assert len({s.food_kind for s in built}) >= 5
assert any(s.last_seen_at is None for s in built)           # never confirmed
assert any(s.stops for s in built)                          # some run rounds
assert any(i.price == 0 for s in built for i in s.items)    # some boards hide rates
assert any(i.price > 0 for s in built for i in s.items)
assert any(s.report_count for s in built)                   # reports queue not empty
# Prices are street-plausible, rounded like a real board.
prices = [i.price for s in built for i in s.items if i.price]
assert all(5 <= p <= 400 and p % 5 == 0 for p in prices)

res = client.post("/api/admin/data/sample",
                  json={"lat": 19.0760, "long": 72.8777, "count": 12, "replace": True}).json()
assert res["created"] == 12 and res["items"] > 0
listing = client.get("/api/food/near", params={
    "lat": 19.0760, "long": 72.8777, "radius_km": 10}).json()
assert listing["count"] >= 1, listing["count"]
# Loading again appends rather than replacing, unless asked.
client.post("/api/admin/data/sample", json={"lat": 19.076, "long": 72.8777, "count": 5})
assert client.get("/api/admin/stats").json()["total_shops"] == 17
assert client.post("/api/admin/data/sample", json={"lat": "abc"}).status_code == 422
assert 'loadSampleData' in panel and 'Load 50 sample jagah' in panel
client.post("/api/admin/data/clear")
print("PASS sample thele (placed near you, varied, wipe-first option)")

# 47k-3. Navigation + the shopkeeper page can hold more than one shop.
panel = client.get("/admin").text
assert 'class="pagelinks"' in panel and 'clearAllData()' in panel
for path in ('href="/"', 'href="/admin"'):
    assert path in panel, path
# /docs is a developer surface — the owner panel shouldn't point at it. The
# route still exists, it's just not advertised here.
assert 'href="/docs"' not in panel
assert client.get("/docs").status_code == 200
# The removed pages must not be linked from anywhere either.
assert "/classic" not in panel and "/shopkeeper" not in panel
assert 'class="ownerlink"' in client.get("/").text
# The food app is served by the Render static site too, which has no API of its
# own — so it must read the backend URL from config.js rather than assume
# same-origin. Getting this wrong breaks every fetch in production only.
home_page = client.get("/").text
assert 'src="/config.js"' in home_page
assert 'window.MYNA_API_BASE' in home_page
print("PASS page navigation")

# 4k-4. Vendors tab: the one management surface, in the food app's terms.
res = client.post("/api/food/add", data={
    "lat": 19.0760, "long": 72.8777, "name": "Admin List Thela", "kind": "chinese",
    "day_of_week": -1, "start_time": "10:00", "end_time": "22:00",
}, files={"photo": ("v.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")})
vend_id = res.json()["vendor"]["shop_id"]
client.post(f"/api/food/{vend_id}/items", json={"name": "Chowmein", "price": 40})

rows = client.get("/api/admin/vendors").json()
row = next(r for r in rows if r["shop_id"] == vend_id)
assert row["kind_label"] == "Chinese thela" and row["kind_emoji"]
assert row["menu_count"] == 1 and row["round_count"] == 1
assert row["seen_yes"] == 1 and row["hidden"] is False
# Search and the kind filter both narrow the list.
assert any(r["shop_id"] == vend_id for r in
           client.get("/api/admin/vendors", params={"q": "admin list"}).json())
assert all(r["shop_id"] != vend_id for r in
           client.get("/api/admin/vendors", params={"kind": "sweets"}).json())
# Renaming fixes the common case: a misread signboard.
assert client.patch(f"/api/admin/shops/{vend_id}",
                    json={"name": "Sudhra Hua Naam"}).json()["name"] == "Sudhra Hua Naam"
# Deleting takes the menu and rounds with it — session delete, so cascade runs.
assert client.delete(f"/api/admin/shops/{vend_id}").status_code == 204
assert client.get(f"/api/food/{vend_id}").status_code == 404
from app import models as _m
from app.database import SessionLocal as _S
_d = _S()
try:
    assert _d.query(_m.Item).filter_by(shop_id=vend_id).count() == 0
    assert _d.query(_m.ShopStop).filter_by(shop_id=vend_id).count() == 0
finally:
    _d.close()
assert client.delete("/api/admin/shops/999999").status_code == 404
assert 'id="tab-vendors"' in panel and "loadVendors()" in panel
# One umbrella word, and it isn't "thela" — a dhaba or restaurant is not a
# cart. "Thela" survives only as the name of the kind that actually is one.
assert '<span class="tab-text">Jagah</span>' in panel
assert '<th>Jagah</th>' in panel
assert "koi thela list" not in panel and "sample thele" not in panel
assert 'id="tab-items"' not in panel and 'id="tab-import"' not in panel
print("PASS vendors tab: list, filter, rename, delete with cascade")

# 47l. Reference data + the food UI itself.
kinds = client.get("/api/food/kinds").json()
assert {"kind", "label", "emoji", "mobile"} <= set(kinds["kinds"][0])
assert "Momos" in kinds["popular"]
assert [r["reason"] for r in kinds["seen_reasons"]][0] == "closed_today"  # gentlest first
assert {"fake", "joke", "duplicate"} <= {r["reason"] for r in kinds["report_reasons"]}
page = client.get("/").text
assert 'id="fab"' in page and "/api/food/near" in page and "/api/food/add" in page
assert "Kya khaana hai?" in page and "Abhi hai ✓" in page
assert "/report" in page and 'class="flag"' in page and "Kyun nahi mila?" in page
print("PASS food reference data + UI")


print("\nALL TESTS PASSED")
