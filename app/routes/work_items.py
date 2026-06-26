from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.equipment import Equipment
from app.models.project import Project
from app.models.work_item import EquipmentWorkItem
from app.services.validation_service import update_project_review_status


router = APIRouter(prefix="/projects/{project_id}", tags=["work-items"])


def _project_or_404(db: Session, project_id: str) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.equipment).selectinload(Equipment.work_items), selectinload(Project.extraction_issues))
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    return project


def _equipment_or_404(project: Project, equipment_id: str) -> Equipment:
    equipment = next((item for item in project.equipment if item.id == equipment_id), None)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipo no encontrado.")
    return equipment


def _work_item_or_404(project: Project, work_item_id: str) -> EquipmentWorkItem:
    for equipment in project.equipment:
        for work_item in equipment.work_items:
            if work_item.id == work_item_id:
                return work_item
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trabajo no encontrado.")


@router.get("/review/work", response_class=HTMLResponse, name="review_work")
def review_work(project_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = _project_or_404(db, project_id)
    return request.app.state.templates.TemplateResponse(request, "projects/review_work.html", {"project": project})


@router.post("/equipment/{equipment_id}/work", name="work_item_create")
def work_item_create(
    project_id: str,
    equipment_id: str,
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    equipment = _equipment_or_404(project, equipment_id)
    if description.strip():
        equipment.work_items.append(
            EquipmentWorkItem(
                equipment_id=equipment.id,
                sequence=len(equipment.work_items) + 1,
                title=title.strip() or None,
                description=description.strip(),
                source_text=description.strip(),
                is_custom=True,
            )
        )
    update_project_review_status(project)
    db.commit()
    return RedirectResponse(request.url_for("review_work", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


@router.put("/work/{work_item_id}", name="work_item_update")
def work_item_update_api(project_id: str, work_item_id: str, payload: dict, db: Session = Depends(get_db)) -> dict[str, str]:
    project = _project_or_404(db, project_id)
    work_item = _work_item_or_404(project, work_item_id)
    _apply_work_item_values(work_item, payload)
    db.commit()
    return {"status": "updated", "work_item_id": work_item.id}


@router.post("/work/{work_item_id}/update", name="work_item_update_form")
def work_item_update_form(
    project_id: str,
    work_item_id: str,
    request: Request,
    title: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    work_item = _work_item_or_404(project, work_item_id)
    _apply_work_item_values(work_item, {"title": title, "description": description})
    db.commit()
    return RedirectResponse(request.url_for("review_work", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


@router.delete("/work/{work_item_id}", name="work_item_delete")
def work_item_delete(project_id: str, work_item_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    project = _project_or_404(db, project_id)
    work_item = _work_item_or_404(project, work_item_id)
    equipment = work_item.equipment
    equipment.work_items.remove(work_item)
    _renumber_work_items(equipment)
    db.commit()
    return {"status": "deleted", "work_item_id": work_item_id}


@router.post("/work/{work_item_id}/delete", name="work_item_delete_form")
def work_item_delete_form(project_id: str, work_item_id: str, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    work_item = _work_item_or_404(project, work_item_id)
    equipment = work_item.equipment
    equipment.work_items.remove(work_item)
    _renumber_work_items(equipment)
    db.commit()
    return RedirectResponse(request.url_for("review_work", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


def _apply_work_item_values(work_item: EquipmentWorkItem, values: dict[str, object]) -> None:
    work_item.title = str(values.get("title") or "").strip() or None
    description = str(values.get("description") or "").strip()
    if description:
        work_item.description = description
        work_item.source_text = work_item.source_text or description
    work_item.is_custom = True


def _renumber_work_items(equipment: Equipment) -> None:
    for index, work_item in enumerate(sorted(equipment.work_items, key=lambda item: item.sequence), start=1):
        work_item.sequence = index
