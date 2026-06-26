from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse


router = APIRouter()


@router.get("/")
def home(request: Request) -> RedirectResponse:
    return RedirectResponse(request.url_for("project_list"))

