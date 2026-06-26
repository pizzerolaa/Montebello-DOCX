from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models.enums import SignatureRole
from app.models.lot import Lot
from app.models.project import Project
from app.models.signature import Signature
from app.services.docx_reader import canonical_text
from app.services.validation_service import resolve_field_issues, update_project_review_status


router = APIRouter(prefix="/projects/{project_id}/review", tags=["review"])


def _project_or_404(db: Session, project_id: str) -> Project:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.lots),
            selectinload(Project.equipment),
            selectinload(Project.signatures),
            selectinload(Project.extraction_issues),
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    return project


@router.get("/general", response_class=HTMLResponse, name="review_general")
def review_general(project_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = _project_or_404(db, project_id)
    return request.app.state.templates.TemplateResponse(request, "projects/review_general.html", {"project": project})


@router.post("/general", name="review_general_update")
def review_general_update(
    project_id: str,
    request: Request,
    name: str = Form(""),
    center_name: str = Form(""),
    location: str = Form(""),
    state: str = Form(""),
    service_date_raw: str = Form(""),
    contract_date_raw: str = Form(""),
    order_number: str = Form(""),
    client_name: str = Form(""),
    lots_text: str = Form(""),
    deliverer_name: str = Form(""),
    deliverer_position: str = Form(""),
    receiver_name: str = Form(""),
    receiver_position: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    project.name = name.strip() or project.name
    for field_name, value in {
        "center_name": center_name,
        "location": location,
        "state": state,
        "service_date_raw": service_date_raw,
        "contract_date_raw": contract_date_raw,
        "order_number": order_number,
        "client_name": client_name,
    }.items():
        setattr(project, field_name, value.strip() or None)

    _sync_lots_from_text(project, lots_text)
    _assign_single_lot_to_unassigned_equipment(project)
    _upsert_signature(project, SignatureRole.DELIVERER.value, deliverer_name, deliverer_position, 1)
    _upsert_signature(project, SignatureRole.RECEIVER.value, receiver_name, receiver_position, 2)
    resolve_field_issues(
        project,
        "Project",
        {"center_name", "location", "state", "service_date_raw", "contract_date_raw", "order_number", "client_name"},
    )
    update_project_review_status(project)
    db.commit()
    return RedirectResponse(request.url_for("review_general", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/issues/{issue_id}/resolve", name="review_issue_resolve")
def review_issue_resolve(project_id: str, issue_id: str, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    issue = next((item for item in project.extraction_issues if item.id == issue_id), None)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aviso no encontrado.")
    issue.resolved = True
    issue.resolved_value = issue.resolved_value or "Resuelto manualmente"
    update_project_review_status(project)
    db.commit()
    referer = request.headers.get("referer")
    return RedirectResponse(referer or request.url_for("review_general", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


def _sync_lots_from_text(project: Project, lots_text: str) -> None:
    lot_numbers = [line.strip() for line in lots_text.splitlines() if line.strip()]
    existing = {canonical_text(lot.lot_number): lot for lot in project.lots}
    keep = {canonical_text(lot_number) for lot_number in lot_numbers}
    for lot in list(project.lots):
        if canonical_text(lot.lot_number) not in keep and not lot.equipment:
            project.lots.remove(lot)
    for lot_number in lot_numbers:
        key = canonical_text(lot_number)
        if key not in existing:
            project.lots.append(Lot(project_id=project.id, lot_number=lot_number))


def _assign_single_lot_to_unassigned_equipment(project: Project) -> None:
    if len(project.lots) != 1:
        return
    lot = project.lots[0]
    for equipment in project.equipment:
        if equipment.lot_id is None:
            equipment.lot = lot


def _upsert_signature(project: Project, role: str, name: str, position: str, sequence: int) -> None:
    clean_name = name.strip()
    clean_position = position.strip()
    if not clean_name and not clean_position:
        return
    signature = next((item for item in project.signatures if item.role == role), None)
    if signature is None:
        signature = Signature(project_id=project.id, role=role, sequence=sequence)
        project.signatures.append(signature)
    signature.name = clean_name or None
    signature.position = clean_position or None
