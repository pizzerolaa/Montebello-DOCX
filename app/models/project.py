from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ProjectStatus
from app.models.time import utc_now


if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.extraction_issue import ExtractionIssue
    from app.models.generated_artifact import GeneratedArtifact
    from app.models.lot import Lot
    from app.models.signature import Signature
    from app.models.source_document import SourceDocument


def new_uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    center_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_date_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_date_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default=ProjectStatus.UPLOADING.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    source_documents: Mapped[list["SourceDocument"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    lots: Mapped[list["Lot"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    equipment: Mapped[list["Equipment"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    signatures: Mapped[list["Signature"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    extraction_issues: Mapped[list["ExtractionIssue"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    generated_artifacts: Mapped[list["GeneratedArtifact"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
