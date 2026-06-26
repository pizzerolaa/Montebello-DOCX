from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db
from app.models.project import Project
from app.services.storage_service import remove_project_files


router = APIRouter(prefix="/projects", tags=["projects"])


def _project_or_404(db: Session, project_id: str) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.source_documents), selectinload(Project.equipment))
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    return project


@router.get("", response_class=HTMLResponse, name="project_list")
def project_list(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    projects = db.scalars(select(Project).order_by(Project.created_at.desc())).all()
    return request.app.state.templates.TemplateResponse(
        request, "projects/list.html", {"projects": projects}
    )


@router.get("/new", response_class=HTMLResponse, name="project_new")
def project_new(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(request, "projects/new.html")


@router.post("", name="project_create")
def project_create(
    request: Request,
    name: str = Form(""),
    center_name: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    clean_name = name.strip() or "Proyecto sin nombre"
    project = Project(name=clean_name, center_name=center_name.strip() or None)
    db.add(project)
    db.commit()
    db.refresh(project)
    return RedirectResponse(request.url_for("project_detail", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{project_id}", response_class=HTMLResponse, name="project_detail")
def project_detail(project_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = _project_or_404(db, project_id)
    return request.app.state.templates.TemplateResponse(
        request, "projects/detail.html", {"project": project}
    )


@router.delete("/{project_id}", name="project_delete")
def project_delete(project_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    project = _project_or_404(db, project_id)
    db.delete(project)
    db.commit()
    remove_project_files(get_settings(), project_id)
    return {"status": "deleted", "project_id": project_id}


@router.post("/{project_id}/delete", name="project_delete_form")
def project_delete_form(project_id: str, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    db.delete(project)
    db.commit()
    remove_project_files(get_settings(), project_id)
    return RedirectResponse(request.url_for("project_list"), status_code=status.HTTP_303_SEE_OTHER)
