from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.routes import router
from app.config import get_settings
from app.storage.local import LocalStorage

settings = get_settings()

app = FastAPI(
    title="ShelfReady API",
    description="AI product-onboarding agent for small e-commerce teams",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "agent_mode": settings.agent_mode}


@app.get("/api/media/{file_path:path}")
def media(file_path: str) -> FileResponse:
    storage = LocalStorage()
    path = storage.absolute(file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Media not found")
    try:
        path.resolve().relative_to(storage.root.resolve())
    except ValueError as exc:
        raise HTTPException(400, "Invalid path") from exc
    return FileResponse(path)


@app.get("/")
def root() -> dict:
    return {
        "name": "ShelfReady",
        "tagline": "From messy supplier data to storefront-ready products.",
        "docs": "/docs",
    }
