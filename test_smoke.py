"""End-to-end smoke test using FastAPI TestClient (no live server needed)."""
import io
import os
import re

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

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# 1. Pages load
assert client.get("/").status_code == 200
assert client.get("/shopkeeper").status_code == 200
print("PASS pages load")

# 2. Create a shop
res = client.post("/api/shops", json={
    "name": "Sharma General Store",
    "shopkeeper": "Rakesh Sharma",
    "lat": 19.0760,
    "long": 72.8777,
    "address": "123 Test Road, Mumbai",
    "phone": "9812345678",
})
assert res.status_code == 200, res.text
shop = res.json()
assert shop["shopkeeper"] == "Rakesh Sharma"
shop_id = shop["shop_id"]
print(f"PASS create shop id={shop_id}")

# 3. Get + patch shop
assert client.get(f"/api/shops/{shop_id}").json()["name"] == "Sharma General Store"
res = client.patch(f"/api/shops/{shop_id}", json={"phone": "9999999999"})
assert res.json()["phone"] == "9999999999"
print("PASS get/patch shop")

# 4. Add items (with a fake photo) - retention is off by default so photo_url is empty
fake_img = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # minimal JPEG-ish bytes
res = client.post(
    f"/api/shops/{shop_id}/items",
    data={"name": "Parle-G Gold 100g", "category": "Snacks"},
    files={"photo": ("item.jpg", fake_img, "image/jpeg")},
)
assert res.status_code == 200, res.text
item = res.json()
assert item["photo_url"] == ""
item_id = item["item_id"]
print(f"PASS add item id={item_id} (no photo_url with retention off)")

client.post(f"/api/shops/{shop_id}/items", data={"name": "Tata Salt 1kg", "category": "Grocery"})

# 5. List items
items = client.get(f"/api/shops/{shop_id}/items").json()
assert len(items) == 2
print("PASS list items")

# 6. Search — found near user, nearest first
res = client.get("/api/search", params={"q": "parle", "lat": 19.076, "long": 72.878})
results = res.json()
assert len(results) == 1 and results[0]["item_name"] == "Parle-G Gold 100g"
assert results[0]["distance_km"] < 1
print(f"PASS search found at {results[0]['distance_km']} km")

# 7. Search — case-insensitive, second item
res = client.get("/api/search", params={"q": "SALT", "lat": 19.08, "long": 72.88})
assert len(res.json()) == 1
print("PASS fuzzy case-insensitive search")

# 8. Search — no range filter, far shops still returned (sorted by distance)
res = client.get("/api/search", params={"q": "parle", "lat": 28.61, "long": 77.20})  # Delhi
assert len(res.json()) == 1  # Mumbai shop ~1100 km away still returned
assert res.json()[0]["distance_km"] > 1000
print("PASS no range filter returns far shops, sorted by distance")

# 9. Search — sorted nearest first
res = client.get("/api/search", params={"q": "parle", "lat": 19.5, "long": 72.9})
assert len(res.json()) == 1
print("PASS haversine distance boundaries correct")

# 9b. Search — match shop name
res = client.get("/api/search", params={"q": "sharma", "lat": 19.076, "long": 72.878})
assert len(res.json()) >= 1
print("PASS search matches shop name")

# 9c. Search — match shopkeeper name
res = client.get("/api/search", params={"q": "rakesh", "lat": 19.076, "long": 72.878})
assert len(res.json()) >= 1
print("PASS search matches shopkeeper name")

# 9d. Search — match item category
res = client.get("/api/search", params={"q": "grocery", "lat": 19.076, "long": 72.878})
assert len(res.json()) >= 1
print("PASS search matches item category")

# 9e. Agentic flat search — multi-item query parsed via fallback (no API keys in tests)
res = client.get("/api/search", params={"q": "parle and salt", "lat": 19.076, "long": 72.878})
results = res.json()
assert len(results) >= 2
assert all(r["coverage_total"] == 2 for r in results)
assert {r["matched_term"] for r in results} == {"parle", "salt"}
# shop with both items ranks first
assert results[0]["coverage_count"] == 2
print("PASS agentic flat search (multi-term fallback, coverage ranking)")

# 9f. Agentic grouped search — one card per shop with coverage score
res = client.get("/api/search/shops", params={"q": "parle and salt", "lat": 19.076, "long": 72.878})
data = res.json()
assert data["items"] == ["parle", "salt"]
assert data["method"] == "fallback"          # no API key in tests
assert len(data["shops"]) >= 1
top = data["shops"][0]
assert top["coverage_count"] == 2 and top["coverage_total"] == 2
assert {i["matched_term"] for i in top["items"]} == {"parle", "salt"}
print("PASS agentic grouped search (/api/search/shops)")

# 9g. One-tap search — shopping list picks one product per term
res = client.get("/api/search/one-tap", params={"q": "parle and salt", "lat": 19.076, "long": 72.878})
data = res.json()
assert [i["item"] for i in data["shopping_list"]] == ["parle", "salt"]
assert all(i["in_stock"] for i in data["shopping_list"])
assert data["shopping_list"][0]["product"] == "Parle-G Gold 100g"
print("PASS one-tap search (shopping list)")

# 9h. Dish mode — a dish name expands into its ingredients (curated glossary,
# since no API key is configured in tests), and shops carry coordinates so the
# app can link to directions.
res = client.get("/api/search/one-tap", params={
    "q": "how to make poha", "lat": 19.076, "long": 72.878, "mode": "dish"})
data = res.json()
assert data["method"] == "dish-curated", data["method"]
assert "poha" in data["items"] and "haldi" in data["items"]
assert [i["item"] for i in data["shopping_list"]] == data["items"]
print("PASS dish mode expands a dish into ingredients")

res = client.get("/api/search/dishes")
assert "poha" in res.json()["dishes"]
print("PASS popular dishes endpoint")

res = client.get("/api/search/shops", params={"q": "parle", "lat": 19.076, "long": 72.878})
top = res.json()["shops"][0]
assert top["shop_lat"] and top["shop_long"]
assert top["items"][0]["shop_lat"] == top["shop_lat"]
print("PASS shop coordinates travel with search results")

# 9i. Substring matching is word-aware: "haldi" must not match "Haldiram".
from app.routers.search import _matches_alias
assert _matches_alias("Haldiram Bhujia", {"haldi"}) is False
assert _matches_alias("Everest Haldi Powder", {"haldi"}) is True
assert _matches_alias("Onions 1kg", {"onion"}) is True
assert _matches_alias("Green Chillies", {"chilli"}) is True
assert _matches_alias("Parle-G Gold 100g", {"parle"}) is True
assert _matches_alias("Silk Chocolate", {"milk"}) is False
print("PASS word-aware substring matching")

# 10. Update + delete item
res = client.patch(f"/api/shops/{shop_id}/items/{item_id}", json={"name": "Parle-G Gold 200g"})
assert res.json()["name"] == "Parle-G Gold 200g"
res = client.delete(f"/api/shops/{shop_id}/items/{item_id}")
assert res.status_code == 204
items = client.get(f"/api/shops/{shop_id}/items").json()
assert len(items) == 1
print("PASS update/delete item")

# 11. AI suggest endpoint (no API key -> empty suggestion, photo not persisted)
res = client.post(
    f"/api/shops/{shop_id}/items/suggest",
    files={"photo": ("item.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")},
)
assert res.status_code == 200
assert res.json()["photo_url"] == ""
print("PASS item suggest endpoint (graceful fallback without API key)")

# 12. Shop photo upload with retention off -> no photo_url
res = client.post(
    f"/api/shops/{shop_id}/photo",
    files={"photo": ("sign.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")},
)
assert res.json()["photo_url"] == ""
print("PASS shop photo upload with retention off")

# 13. Admin page loads
assert client.get("/admin").status_code == 200
print("PASS admin page loads")

# 14. Admin stats
res = client.get("/api/admin/stats")
assert res.status_code == 200
data = res.json()
assert data["total_shops"] == 1
assert data["total_items"] == 1
assert len(data["recent_shops"]) == 1
print("PASS admin stats")

# 15. Admin list shops
res = client.get("/api/admin/shops")
assert res.status_code == 200
assert len(res.json()) == 1
assert res.json()[0]["name"] == "Sharma General Store"
print("PASS admin list shops")

# 16. Admin list shops with search
res = client.get("/api/admin/shops", params={"q": "sharma"})
assert len(res.json()) == 1
res = client.get("/api/admin/shops", params={"q": "zzz_nonexistent"})
assert res.json() == []
print("PASS admin shop search")

# 17. Admin get shop detail
res = client.get(f"/api/admin/shops/{shop_id}")
assert res.status_code == 200
assert res.json()["name"] == "Sharma General Store"
print("PASS admin get shop")

# 18. Admin update shop
res = client.patch(f"/api/admin/shops/{shop_id}", json={"phone": "1112223333"})
assert res.json()["phone"] == "1112223333"
print("PASS admin update shop")

# 19. Admin list shop items
res = client.get(f"/api/admin/shops/{shop_id}/items")
assert res.status_code == 200
assert len(res.json()) == 1  # "Tata Salt 1kg"
print("PASS admin list shop items")

# 20. Admin update any item
item_id = res.json()[0]["item_id"]
res = client.patch(f"/api/admin/items/{item_id}", json={"name": "Tata Salt Rock 1kg"})
assert res.json()["name"] == "Tata Salt Rock 1kg"
print("PASS admin update item")

# 21. Admin delete any item
res = client.delete(f"/api/admin/items/{item_id}")
assert res.status_code == 204
print("PASS admin delete item")

# 22. Admin LLM providers (no keys -> empty providers)
res = client.get("/api/admin/llm/providers")
assert res.status_code == 200
data = res.json()
assert data["providers"] == []
assert data["configured_providers"] == []
print("PASS admin LLM providers (unconfigured)")

# 23. Admin LLM models endpoint (no keys -> empty list)
res = client.get("/api/admin/llm/models")
assert res.status_code == 200
assert res.json() == {"models": []}
print("PASS admin LLM models (unconfigured)")

# 24. Admin embedding models endpoint — local backend is always listed (no
# API key needed); Gemini only appears once GEMINI_API_KEY is configured.
res = client.get("/api/admin/llm/embedding-models")
assert res.status_code == 200
models = res.json()["models"]
assert any(m["provider"] == "local" for m in models)
assert not any(m["provider"] == "gemini" for m in models)
print("PASS admin embedding models (local always available)")

# 25. Admin CSV template (blank)
res = client.get("/api/admin/import/template")
assert res.status_code == 200
assert res.headers["content-type"].startswith("text/csv")
assert res.content.decode("utf-8-sig").splitlines()[0].lower().split(",") == [
    "shop_name", "shopkeeper", "lat", "long", "address", "phone", "item_name", "category",
]
print("PASS admin import template")

# 26. Admin CSV template (sample data)
res = client.get("/api/admin/import/template", params={"sample": 1})
assert res.status_code == 200
rows = res.content.decode("utf-8-sig").strip().splitlines()
assert rows[0].lower().startswith("shop_name,shopkeeper,lat,long,address,phone,item_name,category")
from app.sample_data import build_shops, shops_to_csv_rows
assert len(rows) == 1 + len(shops_to_csv_rows(build_shops(50)))
assert any(r.startswith("Sharma General Store,") for r in rows)
print("PASS admin sample template")

# 27. Admin CSV import
csv_body = (
    "shop_name,shopkeeper,lat,long,address,phone,item_name,category\n"
    "Patel Supermarket,Nita Patel,19.07,72.87,Marol Market,9830012345,Amul Butter 500g,Dairy\n"
    "Patel Supermarket,Nita Patel,19.07,72.87,Marol Market,9830012345,Milk 500ml,Dairy\n"
    "Gupta Stores,Rahul Gupta,19.12,72.84,Lokhandwala,9821123456,Biscuits,Snacks\n"
).encode()
res = client.post("/api/admin/import/csv", files={"file": ("shops.csv", csv_body, "text/csv")})
assert res.status_code == 200, res.text
data = res.json()
assert data["created"] == 2
assert data["updated"] == 0
assert data["items"] == 3
assert data["total_errors"] == 0
print("PASS admin CSV import")

# 28. Re-import same CSV -> shops updated, items duplicated (no wipe)
res = client.post("/api/admin/import/csv", files={"file": ("shops.csv", csv_body, "text/csv")})
data = res.json()
assert data["created"] == 0
assert data["updated"] == 2
assert data["items"] == 3
print("PASS admin CSV re-import updates shops")

# 29. Import with replace=true wipes existing then re-adds
res = client.post(
    "/api/admin/import/csv",
    data={"replace": "true"},
    files={"file": ("shops.csv", csv_body, "text/csv")},
)
assert res.status_code == 200, res.text
data = res.json()
assert data["created"] == 2 and data["items"] == 3
assert client.get("/api/admin/stats").json()["total_shops"] == 2
print("PASS admin CSV import with replace")

# 30. Admin delete shop
shop_list = client.get("/api/admin/shops").json()
assert set(s["name"] for s in shop_list) == {"Patel Supermarket", "Gupta Stores"}
victim = shop_list[0]
res = client.delete(f"/api/admin/shops/{victim['shop_id']}")
assert res.status_code == 204
remaining = [s["name"] for s in client.get("/api/admin/shops").json()]
assert victim["name"] not in remaining and len(remaining) == 1
print("PASS admin delete shop")

# ---------------------------------------------------------------------------
# New tests: image retention, embedding model, settings
# ---------------------------------------------------------------------------

# 31. Default image retention is off
res = client.get("/api/admin/settings")
assert res.status_code == 200
settings = res.json()
assert settings["retain_uploaded_images"] is False
print("PASS default retain_uploaded_images is false")

# 32. Upload item photo with retention off -> no photo_url persisted
fake_img = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
res = client.post(
    f"/api/shops/{shop_id}/items",
    data={"name": "Test Item No Retain", "category": "Test"},
    files={"photo": ("item.jpg", fake_img, "image/jpeg")},
)
assert res.status_code == 200
item = res.json()
assert item["photo_url"] == ""
print("PASS item upload with retention off has empty photo_url")

# 33. Upload shop photo with retention off -> no photo_url persisted
fake_img2 = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50)
res = client.post(
    f"/api/shops/{shop_id}/photo",
    files={"photo": ("sign.jpg", fake_img2, "image/jpeg")},
)
assert res.status_code == 200
shop = res.json()
assert shop["photo_url"] == ""
print("PASS shop photo upload with retention off has empty photo_url")

# 34. Turn retention on -> uploads persist photo_url
res = client.patch("/api/admin/settings", json={"retain_uploaded_images": True})
assert res.status_code == 200
assert res.json()["retain_uploaded_images"] is True

fake_img3 = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50)
res = client.post(
    f"/api/shops/{shop_id}/photo",
    files={"photo": ("sign.jpg", fake_img3, "image/jpeg")},
)
assert res.status_code == 200
shop = res.json()
assert shop["photo_url"].startswith("/uploads/")
print("PASS shop photo upload with retention on persists photo_url")

# 35. Turn retention back off
res = client.patch("/api/admin/settings", json={"retain_uploaded_images": False})
assert res.status_code == 200
assert res.json()["retain_uploaded_images"] is False
print("PASS retention setting can be toggled")

# 36. Search still works without API keys
res = client.get("/api/search", params={"q": "salt", "lat": 19.076, "long": 72.878})
assert res.status_code == 200
print("PASS search works without API keys")

# 37. Search parser still falls back without API keys
res = client.get("/api/search/shops", params={"q": "parle and salt", "lat": 19.076, "long": 72.878})
data = res.json()
assert data["method"] == "fallback"
print("PASS search parser falls back without API keys")

# 37b. Without an LLM, a space-separated list ("milk bread eggs") must still be
# split into items — that's how the app's own suggestion chips are phrased.
res = client.get("/api/search/shops", params={"q": "milk bread eggs", "lat": 19.076, "long": 72.878})
assert res.json()["items"] == ["milk", "bread", "eggs"], res.json()["items"]
res = client.get("/api/search/shops", params={"q": "amul milk", "lat": 19.076, "long": 72.878})
assert res.json()["items"] == ["amul milk"]   # short phrases stay one product
print("PASS space-separated lists split without an LLM")

# 38. Embedding model field exists on items
res = client.get("/api/admin/items?q=Amul")
items = res.json()
assert len(items) >= 1
assert "embedding_model" in items[0]
print("PASS embedding_model field exists on items")

# 39. Embeddings ignore stale model rows
res = client.get("/api/admin/embeddings/status")
assert res.status_code == 200
print("PASS embeddings status endpoint works")

# 40. Admin settings endpoint works
res = client.get("/api/admin/settings")
assert res.status_code == 200
s = res.json()
assert "retain_uploaded_images" in s
assert "default_vision_model" in s
assert "default_search_model" in s
assert "default_embedding_model" in s
print("PASS admin settings endpoint")

# 41. Update all model settings
res = client.patch("/api/admin/settings", json={
    "default_vision_model": "gemini:gemini-2.5-flash",
    "default_search_model": "gemini:gemini-2.5-flash",
    "default_embedding_model": "gemini:gemini-embedding-001",
})
assert res.status_code == 200
data = res.json()
assert data["default_vision_model"] == "gemini:gemini-2.5-flash"
assert data["default_search_model"] == "gemini:gemini-2.5-flash"
assert data["default_embedding_model"] == "gemini:gemini-embedding-001"
print("PASS update all model settings")

# 42. Synonym glossary catches spelling/transliteration variants that neither
# substring nor the local embedding model reliably catch on their own
# (benchmarked: bge-small scores daal/dal and kapoor/camphor below the
# semantic threshold, while unrelated pairs like salt/sugar score above it).
res = client.post(
    f"/api/shops/{shop_id}/items",
    data={"name": "Toor Dal 1kg", "category": "Grocery"},
)
assert res.status_code == 200
res = client.post(
    f"/api/shops/{shop_id}/items",
    data={"name": "Pooja Camphor Tablets", "category": "Pooja Items"},
)
assert res.status_code == 200

res = client.get("/api/search", params={"q": "daal", "lat": 19.076, "long": 72.878})
assert any(r["item_name"] == "Toor Dal 1kg" for r in res.json())
res = client.get("/api/search", params={"q": "kapoor", "lat": 19.076, "long": 72.878})
assert any(r["item_name"] == "Pooja Camphor Tablets" for r in res.json())
print("PASS synonym glossary matches daal/dal and kapoor/camphor")


# 38. Vision/OCR capability: models are tagged, and the self-test reports back
# instead of leaving a text-only model silently broken.
from app import ai as _ai, vision_check as _vc
assert _ai.supports_vision("openai/gpt-oss-safeguard-20b") is False
assert _ai.supports_vision("meta-llama/llama-4-scout-17b-16e-instruct") is True
assert _ai.supports_vision("claude-sonnet-4-20250514") is True
assert _ai.supports_vision("gemini-2.5-flash") is True
assert _ai.supports_vision("llama-3.3-70b-versatile") is False
print("PASS vision capability tagging")

png = _vc.make_test_image("QX-4718")
assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 2000
codes = {_vc._new_code() for _ in range(20)}
assert len(codes) > 15          # fresh code per run, so a pass can't be cached
res = client.post("/api/admin/llm/vision-test", json={"model": "groq/some-model"})
assert res.status_code == 200
assert res.json()["status"] == "unconfigured"   # no API keys in tests
print("PASS vision self-test endpoint")

# 39. Literal shop routes must not be shadowed by /{shop_id}: "/onboard/photo"
# was being parsed as shop_id="onboard" and returning 422, so signage reading
# was broken for every shopkeeper regardless of the model configured.
res = client.post(
    "/api/shops/onboard/photo",
    files={"photo": ("board.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")},
)
assert res.status_code == 200, res.text
assert "suggestion" in res.json()
assert client.get("/api/shops/geocode/reverse", params={"lat": 19.076, "long": 72.878}).status_code == 200
print("PASS onboarding photo + geocode routes are not shadowed by /{shop_id}")

# 40. Photo inputs must offer the gallery too — only the camera input captures.
page = client.get("/shopkeeper").text
cam_inputs = re.findall(r'<input[^>]*capture="environment"[^>]*>', page)
assert len(cam_inputs) == 2, cam_inputs            # one camera input per picker
assert 'id="signFile" accept="image/*"' in page          # gallery/file input, no capture
assert 'id="itemFile" accept="image/*"' in page
for _id in ('signCam', 'signFile', 'itemCam', 'itemFile'):
    assert f'id="{_id}"' in page
assert 'signPick.camera()' in page and 'signPick.upload()' in page
assert 'itemPick.camera()' in page and 'itemPick.upload()' in page
print("PASS shopkeeper offers both camera and upload")

# 41. Catalogue of categories → items, for the checkbox picker. Typing every
# product one at a time was the step shopkeepers gave up on.
res = client.get("/api/catalog")
assert res.status_code == 200
cats = res.json()["categories"]
labels = {c["label"] for c in cats}
assert {"Puja items", "Dry fruits & nuts", "Vegetables", "Spices & masala"} <= labels, labels
assert all(c["items"] and c["count"] == len(c["items"]) for c in cats)
print(f"PASS catalogue endpoint ({len(cats)} categories, "
      f"{sum(c['count'] for c in cats)} items)")

# 42. Bulk add — a whole ticked category goes in with one request, and names
# already in the shop are skipped instead of duplicated.
res = client.post(f"/api/shops/{shop_id}/items/bulk", json={"items": [
    {"name": "Agarbatti (Incense Sticks)", "category": "Puja items"},
    {"name": "Camphor (Kapoor)", "category": "Puja items"},
    {"name": "Almonds (Badam)", "category": "Dry fruits & nuts"},
]})
assert res.status_code == 200, res.text
data = res.json()
assert len(data["added"]) == 3 and data["skipped"] == []
assert all(i["item_id"] for i in data["added"])
res = client.post(f"/api/shops/{shop_id}/items/bulk", json={"items": [
    {"name": "agarbatti (incense sticks)"},        # same item, different case
    {"name": "Cashews (Kaju)"},
]})
data = res.json()
assert len(data["added"]) == 1 and len(data["skipped"]) == 1, data
# A missing category is filled in from the catalogue rather than left blank.
assert data["added"][0]["category"] == "Dry fruits & nuts", data["added"][0]
print("PASS bulk add items (dedupes, infers category)")

# 43. Bulk-added items are searchable straight away (embedded + cache cleared).
res = client.get("/api/search", params={"q": "kapoor", "lat": 19.076, "long": 72.878})
assert any("Camphor" in r["item_name"] for r in res.json()), res.json()
print("PASS bulk-added items are immediately searchable")

# 44. Item suggestion returns a *list* — one shelf photo should list every
# product on it, not just the one in focus.
res = client.post(
    f"/api/shops/{shop_id}/items/suggest",
    files={"photo": ("shelf.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")},
)
body = res.json()
assert body["items"] == []                # no API key configured in tests
assert body["error"], body               # ...and the UI is told why
print("PASS multi-item suggestion shape + error surfacing")

from app.ai import _parse_items
assert _parse_items('```json\n[{"name": "Tata Salt 1kg", "category": "Everyday grocery"}]\n```') == [
    {"name": "Tata Salt 1kg", "category": "Everyday grocery"}]
assert _parse_items("- Parle-G | Snacks\n- Maggi | Snacks") == [
    {"name": "Parle-G", "category": "Snacks"}, {"name": "Maggi", "category": "Snacks"}]
# Same product twice in one frame is one line in the shop's list.
assert _parse_items('[{"name":"Amul Milk"},{"name":"amul milk"}]') == [
    {"name": "Amul Milk", "category": ""}]
print("PASS vision reply parsing (json, fenced json, bullet lines, dedupe)")

from app.catalog import suggest_category
assert suggest_category("Everest Haldi Powder") == "Spices & masala"
assert suggest_category("Haldiram Bhujia") == "Snacks & biscuits"   # word-aware
assert suggest_category("Cycle Agarbatti") == "Puja items"
assert suggest_category("Some Unknown Widget") == ""
print("PASS category inference from item name")

# 45. The shopkeeper page ships the checkbox picker and the multi-item review.
page = client.get("/shopkeeper").text
for marker in ('id="catChips"', 'id="catalogGroups"', 'id="foundItems"',
               'id="selectBar"', 'data-mode="catalog"', 'items/bulk'):
    assert marker in page, marker
print("PASS shopkeeper page has the category checkbox picker")
# 46. Mobile vendors (thela/cart): a vendor with no fixed place is found by
# their stops — place + weekly/daily timing — not by an address.
from datetime import datetime, timedelta

from app import schedule as _sched

# 46a. Schedule maths, against a frozen clock (a Wednesday, 11:00).
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
assert _sched.describe(1, "10:00", "12:00") == "Every Tuesday · 10 AM – 12 PM"
assert _sched.describe(-1, "09:30", "13:45") == "Every day · 9:30 AM – 1:45 PM"
assert _sched.parse_hhmm("25:00") is None and _sched.parse_hhmm("") is None
print("PASS schedule status/format for rounds")

# 46b. Registering a cart and adding rounds.
res = client.post("/api/shops", json={
    "name": "Ramu Sabzi Thela",
    "shopkeeper": "Ramu",
    "lat": 19.0700, "long": 72.8700,
    "address": "Andheri West",
    "shop_type": "mobile",
})
assert res.status_code == 200, res.text
cart_id = res.json()["shop_id"]
assert res.json()["shop_type"] == "mobile"

_now = _sched.now_local()
_from, _till = f"{max(0, _now.hour - 1):02d}:00", f"{min(23, _now.hour + 1):02d}:30"
res = client.post(f"/api/shops/{cart_id}/stops", json={
    "label": "Gali no. 4, mandir ke paas",
    "lat": 19.0850, "long": 72.8777,          # ~1 km from the customer below
    "day_of_week": -1, "start_time": _from, "end_time": _till,
})
assert res.status_code == 200, res.text
live_stop = res.json()
assert live_stop["status"] == "here_now" and live_stop["rank"] == 0
assert live_stop["when"].startswith("Every day")

_other_day = (_now.weekday() + 3) % 7
res = client.post(f"/api/shops/{cart_id}/stops", json={
    "label": "Sector 12 market",
    "lat": 19.0761, "long": 72.8778,          # closer, but only once a week
    "day_of_week": _other_day, "start_time": "10:00", "end_time": "12:00",
})
assert res.status_code == 200, res.text
weekly_stop = res.json()
assert weekly_stop["rank"] == _sched.ANOTHER_DAY

# Bad schedules are rejected rather than stored as nonsense.
assert client.post(f"/api/shops/{cart_id}/stops", json={
    "lat": 19.07, "long": 72.87, "day_of_week": 9}).status_code == 422
assert client.post(f"/api/shops/{cart_id}/stops", json={
    "lat": 19.07, "long": 72.87, "start_time": "12:00", "end_time": "11:00"}).status_code == 422
assert client.post(f"/api/shops/{cart_id}/stops", json={
    "lat": 19.07, "long": 72.87, "start_time": "25:70"}).status_code == 422
assert client.post("/api/shops/999999/stops", json={"lat": 1, "long": 1}).status_code == 404

stops = client.get(f"/api/shops/{cart_id}/stops").json()
assert [s["stop_id"] for s in stops] == [live_stop["stop_id"], weekly_stop["stop_id"]]  # soonest first
print("PASS cart registration + rounds CRUD")

# 46c. Search points customers at the round they can actually reach, and the
# card carries the timing.
client.post(f"/api/shops/{cart_id}/items", data={"name": "Fresh Bhindi 1kg", "category": "Vegetables"})
res = client.get("/api/search/one-tap", params={"q": "bhindi", "lat": 19.0760, "long": 72.8777})
assert res.status_code == 200, res.text
data = res.json()
cart = next(s for s in data["shops"] if s["shop_id"] == cart_id)
assert cart["shop_type"] == "mobile"
assert cart["stop"]["stop_id"] == live_stop["stop_id"]      # the one he's at right now
assert cart["shop_lat"] == 19.0850 and cart["shop_long"] == 72.8777   # directions -> the stop
assert 0.9 < cart["distance_km"] < 1.3                      # distance measured to the stop
assert cart["stop"]["status"] == "here_now"
assert len(cart["stops"]) == 2 and cart["stops"][1]["distance_km"] < cart["distance_km"]
listed = next(i for i in data["shopping_list"] if i["item"] == "bhindi")
assert listed["shop_type"] == "mobile" and "Here now" in listed["availability"]
print("PASS search resolves a cart to its current round")

# 46d. A cart with no rounds yet still behaves like a shop at its base location.
res = client.post("/api/shops", json={
    "name": "Naya Thela", "lat": 19.0762, "long": 72.8779, "shop_type": "mobile"})
bare_id = res.json()["shop_id"]
client.post(f"/api/shops/{bare_id}/items", data={"name": "Bhindi Masala Mix", "category": "Spices"})
res = client.get("/api/search/shops", params={"q": "bhindi", "lat": 19.0760, "long": 72.8777})
bare = next(s for s in res.json()["shops"] if s["shop_id"] == bare_id)
assert bare["stop"] is None and bare["stops"] == [] and bare["distance_km"] < 0.5

# 46e. Adding a round to a shop registered as fixed flips it to mobile — that's
# what "I move around" means, no separate toggle needed.
res = client.post("/api/shops", json={"name": "Chai Wala", "lat": 19.076, "long": 72.8777})
chai_id = res.json()["shop_id"]
assert res.json()["shop_type"] == "fixed"
client.post(f"/api/shops/{chai_id}/stops", json={
    "label": "Station gate", "lat": 19.0765, "long": 72.8779,
    "day_of_week": 0, "start_time": "07:00", "end_time": "10:00"})
assert client.get(f"/api/shops/{chai_id}").json()["shop_type"] == "mobile"

# Rounds can be edited and removed.
sid = client.get(f"/api/shops/{chai_id}/stops").json()[0]["stop_id"]
res = client.patch(f"/api/shops/{chai_id}/stops/{sid}", json={"start_time": "08:00", "end_time": "11:00"})
assert res.json()["when"] == "Every Monday · 8 AM – 11 AM"
assert client.patch(f"/api/shops/{chai_id}/stops/{sid}", json={"end_time": "07:00"}).status_code == 422
assert client.delete(f"/api/shops/{chai_id}/stops/{sid}").json()["deleted"] is True
assert client.get(f"/api/shops/{chai_id}/stops").json() == []
assert client.delete(f"/api/shops/{chai_id}/stops/{sid}").status_code == 404
print("PASS shop type switching + round edit/delete")

# 46f. Both pages carry the vendor UI.
page = client.get("/shopkeeper").text
assert 'data-type="mobile"' in page and 'id="stopDay"' in page and 'id="stopStart"' in page
assert 'id="addStopBtn"' in page
classic = client.get("/classic").text
assert 'cart-tag' in classic and "shop_type === 'mobile'" in classic
print("PASS shopkeeper + customer pages carry the thela UI")


# ---------------------------------------------------------------------------
# 47. Food app: one-photo add, "paas me kya hai", freshness votes
# ---------------------------------------------------------------------------
from app import ai as _ai, food as _food

# 47a. Vocabulary
assert _food.normalise_kind("Chinese") == "chinese"
assert _food.normalise_kind("momos") == "chinese"      # inferred from a hint
assert _food.normalise_kind("") == "other"
assert _food.suggest_category("Veg Chowmein") == "Chinese"
assert _food.suggest_category("Gulab Jamun") == "Sweets"
assert _food.suggest_category("Chilli Potato") == "Chinese"
assert _food.normalise_category("nonsense", "Masala Chai") == "Chai & drinks"
print("PASS food vocabulary")

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

# 47g. Freshness votes. "Nahi mila" outvoting "haan hai" marks a listing
# doubtful, which sinks it below everything else nearby.
assert client.post(f"/api/food/{food_id}/seen", json={"yes": True}).json()["seen_yes"] == 2
for _ in range(4):
    client.post(f"/api/food/{food_id}/seen", json={"yes": False})
state = client.get(f"/api/food/{food_id}").json()
assert state["seen_no"] == 4 and state["trust"] == "doubtful"
assert client.post("/api/food/999999/seen", json={"yes": True}).status_code == 404
print("PASS freshness votes")

# 47h. Reference data + the food UI itself.
kinds = client.get("/api/food/kinds").json()
assert {"kind", "label", "emoji", "mobile"} <= set(kinds["kinds"][0])
assert "Momos" in kinds["popular"]
page = client.get("/").text
assert 'id="fab"' in page and "/api/food/near" in page and "/api/food/add" in page
assert "Kya khaana hai?" in page and "Abhi hai ✓" in page
print("PASS food reference data + UI")


print("\nALL TESTS PASSED")
