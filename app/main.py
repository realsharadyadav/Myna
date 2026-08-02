from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR
from .database import Base, engine
from .routers import admin, items, search, shops

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Myna — Hyperlocal Shop & Product Finder")

app.include_router(shops.router)
app.include_router(items.router)
app.include_router(search.router)
app.include_router(admin.router)

app.mount("/uploads", StaticFiles(directory=BASE_DIR / "uploads"), name="uploads")
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "app" / "static" / "index.html")


@app.get("/shopkeeper", include_in_schema=False)
def shopkeeper():
    return FileResponse(BASE_DIR / "app" / "static" / "shopkeeper.html")


@app.get("/admin", include_in_schema=False)
def admin():
    return FileResponse(BASE_DIR / "app" / "static" / "admin.html")
