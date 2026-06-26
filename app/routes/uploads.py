from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.exceptions import DocumentAppError
from app.models.enums import DetectedProfile, ProcessingStatus
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.services.merge_service import analyze_project
from app.services.storage_service import remove_file, store_docx_upload


router = APIRouter(prefix="/projects/{project_id}", tags=["uploads"])


def _project_or_404(db: Session, project_id: str) -> Project:
    project = db.scalar(
        select(Project).where(Project.id == project_id).options(selectinload(Project.source_documents))
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    return project


@router.get("/upload", response_class=HTMLResponse, name="project_upload")
def upload_form(project_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = _project_or_404(db, project_id)
    return request.app.state.templates.TemplateResponse(
        request, "projects/upload.html", {"project": project, "messages": []}
    )


@router.get("/analysis", response_class=HTMLResponse, name="project_analysis")
def analysis_result(project_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.source_documents),
            selectinload(Project.lots),
            selectinload(Project.equipment),
            selectinload(Project.extraction_issues),
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    counts: dict[str, int] = {}
    for equipment in project.equipment:
        counts[equipment.equipment_type] = counts.get(equipment.equipment_type, 0) + 1
    return request.app.state.templates.TemplateResponse(
        request, "projects/analysis.html", {"project": project, "counts": counts}
    )


@router.post("/documents", response_class=HTMLResponse, name="project_documents_create")
async def documents_create(
    project_id: str,
    request: Request,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    project = _project_or_404(db, project_id)
    messages: list[str] = []
    existing_count = len(project.source_documents)
    if existing_count + len(files) > settings.max_files_per_project:
        messages.append(f"El proyecto no puede tener mas de {settings.max_files_per_project} archivos.")
        return request.app.state.templates.TemplateResponse(
            request, "projects/upload.html", {"project": project, "messages": messages}, status_code=400
        )

    known_hashes = {document.sha256 for document in project.source_documents if document.sha256}
    for upload in files:
        document_id = str(uuid.uuid4())
        try:
            stored = await store_docx_upload(upload, project_id=project.id, document_id=document_id, settings=settings)
            if stored.sha256 in known_hashes:
                remove_file(str(stored.stored_path))
                messages.append(f"{stored.original_filename}: ya fue cargado en este proyecto.")
                continue
            known_hashes.add(stored.sha256)
            db.add(
                SourceDocument(
                    id=document_id,
                    project_id=project.id,
                    original_filename=stored.original_filename,
                    safe_filename=stored.safe_filename,
                    stored_path=str(stored.stored_path),
                    sha256=stored.sha256,
                    file_size=stored.file_size,
                    detected_profile=DetectedProfile.UNKNOWN.value,
                    processing_status=ProcessingStatus.UPLOADED.value,
                )
            )
        except DocumentAppError as exc:
            failed_name = upload.filename or "archivo sin nombre"
            db.add(
                SourceDocument(
                    id=document_id,
                    project_id=project.id,
                    original_filename=failed_name,
                    safe_filename=failed_name,
                    processing_status=ProcessingStatus.FAILED.value,
                    detected_profile=DetectedProfile.UNKNOWN.value,
                )
            )
            messages.append(f"{failed_name}: {exc}")
    db.commit()

    if messages:
        db.refresh(project)
        return request.app.state.templates.TemplateResponse(
            request, "projects/upload.html", {"project": project, "messages": messages}, status_code=400
        )
    return RedirectResponse(request.url_for("project_detail", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/analyze", name="project_analyze")
def project_analyze(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    project = db.scalar(
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.source_documents),
            selectinload(Project.lots),
            selectinload(Project.equipment),
            selectinload(Project.extraction_issues),
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    analyze_project(db, project)
    return RedirectResponse(request.url_for("project_analysis", project_id=project.id), status_code=status.HTTP_303_SEE_OTHER)


@router.delete("/documents/{document_id}", name="project_document_delete")
def document_delete(project_id: str, document_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    project = _project_or_404(db, project_id)
    document = next((item for item in project.source_documents if item.id == document_id), None)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
    remove_file(document.stored_path)
    db.delete(document)
    db.commit()
    return {"status": "deleted", "document_id": document_id}


@router.post("/documents/{document_id}/delete", name="project_document_delete_form")
def document_delete_form(
    project_id: str,
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    project = _project_or_404(db, project_id)
    document = next((item for item in project.source_documents if item.id == document_id), None)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado.")
    remove_file(document.stored_path)
    db.delete(document)
    db.commit()
    return RedirectResponse(request.url_for("project_detail", project_id=project_id), status_code=status.HTTP_303_SEE_OTHER)
