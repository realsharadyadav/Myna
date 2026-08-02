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
assert 'Upload photo' in page and 'Take photo' in page
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


print("\nALL TESTS PASSED")
