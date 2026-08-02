"""End-to-end smoke test using FastAPI TestClient (no live server needed)."""
import io
import os

# Use a throwaway test DB so repeated runs don't accumulate data.
_test_db = "test_myna_smoke.db"
os.environ["DATABASE_URL"] = f"sqlite:///./{_test_db}"

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
    "lat": 19.0760,
    "long": 72.8777,
    "address": "123 Test Road, Mumbai",
    "phone": "9812345678",
})
assert res.status_code == 200, res.text
shop = res.json()
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

# 6. Search — within range (same coords)
res = client.get("/api/search", params={"q": "parle", "lat": 19.076, "long": 72.878, "range_km": 5})
results = res.json()
assert len(results) == 1 and results[0]["item_name"] == "Parle-G Gold 100g"
assert results[0]["distance_km"] < 1
print(f"PASS search found at {results[0]['distance_km']} km")

# 7. Search — case-insensitive, second item
res = client.get("/api/search", params={"q": "SALT", "lat": 19.08, "long": 72.88, "range_km": 5})
assert len(res.json()) == 1
print("PASS fuzzy case-insensitive search")

# 8. Search — outside range returns nothing
res = client.get("/api/search", params={"q": "parle", "lat": 28.61, "long": 77.20, "range_km": 5})  # Delhi
assert res.json() == []
print("PASS range filter excludes far shops")

# 9. Search — wider range from Delhi finds it
res = client.get("/api/search", params={"q": "parle", "lat": 28.61, "long": 77.20, "range_km": 50})
assert res.json() == []  # Mumbai is >50km, still excluded
res = client.get("/api/search", params={"q": "parle", "lat": 19.5, "long": 72.9, "range_km": 50})
assert len(res.json()) == 1
print("PASS haversine distance boundaries correct")

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

# 22. Admin LLM providers (no keys -> empty)
res = client.get("/api/admin/llm/providers")
assert res.status_code == 200
data = res.json()
assert data["providers"] == []
assert data["default_model"] is None
print("PASS admin LLM providers (unconfigured)")

# 23. Admin delete shop
res = client.delete(f"/api/admin/shops/{shop_id}")
assert res.status_code == 204
assert client.get("/api/admin/shops").json() == []
print("PASS admin delete shop")

print("\nALL TESTS PASSED")
