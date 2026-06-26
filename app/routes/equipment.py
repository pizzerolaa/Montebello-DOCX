from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.equipment import Equipment
from app.models.enums import EquipmentType
from app.models.project import Project
from app.services.validation_service import update_project_review_status


router = APIRouter(prefix="/projects/{project_id}", tags=["equipment"])


def _project_or_404(db: Session, project_id: str) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.lots),
            selectinload(Project.equipment).selectinload(Equipment.work_items),
            selectinload(Project.extraction_issues),
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    return project


def _equipment_or_404(project: Project, equipment_id: str) -> Equipment:
    equipment = next((item for item in project.equipment if item.id == equipment_id), None)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipo no encontrado.")
    return equipment


@router.get("/review/equipment", response_class=HTMLResponse, name="review_equipment")
def review_equipment(project_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = _project_or_404(db, project_id)
    return request.app.state.templates.TemplateResponse(request, "projects/review_equipment.html", {"project": project})


@router.post("/equipment", name="equipment_create")
def equipment_create(
    project_id: str,
    request: Request,
    lot_id: str = Form(""),
    equipment_type: str = Form(EquipmentType.UNKNOWN.value),
    zone: str = Form(""),
    brand: str = Form(""),
    capacity: str = Form(""),
    serial: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    project.equipment.append(
        Equipment(
            project_id=project.id,
            lot_id=lot_id or None,
            sequence=len(project.equipment) + 1,
            equipment_type=equipment_type,
            zone=zone.strip() or None,
            brand=brand.strip() or None,
            capacity=capacity.strip() or None,
            serial=serial.strip() or None,
            notes=notes.strip() or None,
            extraction_confidence=1.0,
        )
    )
    update_project_review_status(project)
    db.commit()
    return RedirectResponse(request.url_for("review_equipment", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


@router.put("/equipment/{equipment_id}", name="equipment_update")
def equipment_update_api(project_id: str, equipment_id: str, payload: dict, db: Session = Depends(get_db)) -> dict[str, str]:
    project = _project_or_404(db, project_id)
    equipment = _equipment_or_404(project, equipment_id)
    _apply_equipment_values(equipment, payload)
    update_project_review_status(project)
    db.commit()
    return {"status": "updated", "equipment_id": equipment.id}


@router.post("/equipment/{equipment_id}/update", name="equipment_update_form")
def equipment_update_form(
    project_id: str,
    equipment_id: str,
    request: Request,
    lot_id: str = Form(""),
    equipment_type: str = Form(EquipmentType.UNKNOWN.value),
    zone: str = Form(""),
    brand: str = Form(""),
    capacity: str = Form(""),
    serial: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    equipment = _equipment_or_404(project, equipment_id)
    _apply_equipment_values(
        equipment,
        {
            "lot_id": lot_id,
            "equipment_type": equipment_type,
            "zone": zone,
            "brand": brand,
            "capacity": capacity,
            "serial": serial,
            "notes": notes,
        },
    )
    _resolve_equipment_issues(project, equipment)
    update_project_review_status(project)
    db.commit()
    return RedirectResponse(request.url_for("review_equipment", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


@router.delete("/equipment/{equipment_id}", name="equipment_delete")
def equipment_delete(project_id: str, equipment_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    project = _project_or_404(db, project_id)
    equipment = _equipment_or_404(project, equipment_id)
    project.equipment.remove(equipment)
    _renumber_equipment(project)
    update_project_review_status(project)
    db.commit()
    return {"status": "deleted", "equipment_id": equipment_id}


@router.post("/equipment/{equipment_id}/delete", name="equipment_delete_form")
def equipment_delete_form(project_id: str, equipment_id: str, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    equipment = _equipment_or_404(project, equipment_id)
    project.equipment.remove(equipment)
    _renumber_equipment(project)
    update_project_review_status(project)
    db.commit()
    return RedirectResponse(request.url_for("review_equipment", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/equipment/{equipment_id}/merge", name="equipment_merge")
def equipment_merge(
    project_id: str,
    equipment_id: str,
    request: Request,
    target_equipment_id: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    source = _equipment_or_404(project, equipment_id)
    target = _equipment_or_404(project, target_equipment_id)
    if source.id == target.id:
        return RedirectResponse(request.url_for("review_equipment", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)
    for field_name in ["lot_id", "equipment_type", "zone", "brand", "capacity", "serial", "notes"]:
        if not getattr(target, field_name) and getattr(source, field_name):
            setattr(target, field_name, getattr(source, field_name))
    for work_item in list(source.work_items):
        source.work_items.remove(work_item)
        target.work_items.append(work_item)
    project.equipment.remove(source)
    for issue in project.extraction_issues:
        if issue.entity_type == "Equipment" and issue.entity_id in {source.id, target.id} and issue.field_name == "duplicate":
            issue.resolved = True
            issue.resolved_value = f"Fusionado en equipo {target.sequence}"
    _renumber_equipment(project)
    update_project_review_status(project)
    db.commit()
    return RedirectResponse(request.url_for("review_equipment", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


def _apply_equipment_values(equipment: Equipment, values: dict[str, object]) -> None:
    for field_name in ["lot_id", "zone", "brand", "capacity", "serial", "notes"]:
        value = values.get(field_name)
        setattr(equipment, field_name, str(value).strip() if value else None)
    equipment.equipment_type = str(values.get("equipment_type") or EquipmentType.UNKNOWN.value)
    equipment.extraction_confidence = 1.0


def _resolve_equipment_issues(project: Project, equipment: Equipment) -> None:
    for issue in project.extraction_issues:
        if issue.entity_type == "Equipment" and issue.entity_id == equipment.id:
            if issue.field_name and getattr(equipment, issue.field_name, None):
                issue.resolved = True
                issue.resolved_value = str(getattr(equipment, issue.field_name))


def _renumber_equipment(project: Project) -> None:
    for index, equipment in enumerate(sorted(project.equipment, key=lambda item: item.sequence), start=1):
        equipment.sequence = index
