from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import close_db_pool, init_db_pool
from .routes.marketing import router as marketing_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db_pool()
    try:
        yield
    finally:
        close_db_pool()


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.include_router(marketing_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
    }
