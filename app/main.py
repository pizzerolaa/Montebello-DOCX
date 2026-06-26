from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import init_db
from app.dependencies import require_auth
from app.routes import equipment, generation, home, projects, review, uploads, work_items


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    (settings.storage_root / "uploads").mkdir(parents=True, exist_ok=True)
    (settings.storage_root / "generated").mkdir(parents=True, exist_ok=True)
    (settings.storage_root / "exports").mkdir(parents=True, exist_ok=True)
    init_db()
    logger.info("application_started")
    yield


app = FastAPI(title=settings.app_name, dependencies=[Depends(require_auth)], lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.state.templates = Jinja2Templates(directory=BASE_DIR / "templates")

app.include_router(home.router)
app.include_router(projects.router)
app.include_router(uploads.router)
app.include_router(review.router)
app.include_router(equipment.router)
app.include_router(work_items.router)
app.include_router(generation.router)


@app.exception_handler(404)
def not_found(request: Request, exc: Exception) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(request, "errors/404.html", status_code=404)
