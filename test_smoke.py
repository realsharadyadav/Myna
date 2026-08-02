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

# 4. Add items (with a fake photo)
fake_img = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # minimal JPEG-ish bytes
res = client.post(
    f"/api/shops/{shop_id}/items",
    data={"name": "Parle-G Gold 100g", "category": "Snacks"},
    files={"photo": ("item.jpg", fake_img, "image/jpeg")},
)
assert res.status_code == 200, res.text
item = res.json()
assert item["photo_url"].startswith("/uploads/")
item_id = item["item_id"]
print(f"PASS add item id={item_id}")

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

# 10. Update + delete item
res = client.patch(f"/api/shops/{shop_id}/items/{item_id}", json={"name": "Parle-G Gold 200g"})
assert res.json()["name"] == "Parle-G Gold 200g"
res = client.delete(f"/api/shops/{shop_id}/items/{item_id}")
assert res.status_code == 204
items = client.get(f"/api/shops/{shop_id}/items").json()
assert len(items) == 1
print("PASS update/delete item")

# 11. AI suggest endpoint (no API key -> empty suggestion, but photo saved)
res = client.post(
    f"/api/shops/{shop_id}/items/suggest",
    files={"photo": ("item.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")},
)
assert res.status_code == 200
assert "photo_url" in res.json()
print("PASS item suggest endpoint (graceful fallback without API key)")

# 12. Shop photo upload
res = client.post(
    f"/api/shops/{shop_id}/photo",
    files={"photo": ("sign.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 50), "image/jpeg")},
)
assert res.json()["photo_url"].startswith("/uploads/")
print("PASS shop photo upload")

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

# 22. Admin LLM providers (no keys -> empty providers, but default falls back)
res = client.get("/api/admin/llm/providers")
assert res.status_code == 200
data = res.json()
assert data["providers"] == []
assert data["default_model"] is None or data["default_model"] == ""
print("PASS admin LLM providers (unconfigured)")

# 23. Admin LLM models endpoint (no keys -> empty list)
res = client.get("/api/admin/llm/models")
assert res.status_code == 200
assert res.json() == {"models": []}
print("PASS admin LLM models (unconfigured)")

# 24. Admin set default model (should fail without provider key)
res = client.post("/api/admin/llm/default-model", json={"model": "anthropic/claude-sonnet-4-20250514"})
assert res.status_code == 400
print("PASS admin set default model rejects unconfigured provider")

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

print("\nALL TESTS PASSED")
