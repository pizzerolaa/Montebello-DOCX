from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    UPLOADING = "UPLOADING"
    ANALYZED = "ANALYZED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    READY = "READY"
    GENERATED = "GENERATED"
    FAILED = "FAILED"


class DetectedProfile(StrEnum):
    ACTA = "ACTA"
    WORK_REPORT = "WORK_REPORT"
    ANNEX = "ANNEX"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class ProcessingStatus(StrEnum):
    UPLOADED = "UPLOADED"
    ANALYZED = "ANALYZED"
    FAILED = "FAILED"


class EquipmentType(StrEnum):
    MINISPLIT = "MINISPLIT"
    PACKAGE = "PACKAGE"
    COLD_ROOM = "COLD_ROOM"
    UNKNOWN = "UNKNOWN"


class SignatureRole(StrEnum):
    COMPANY_REPRESENTATIVE = "COMPANY_REPRESENTATIVE"
    DELIVERER = "DELIVERER"
    RECEIVER = "RECEIVER"
    MEDICAL_UNIT_RESPONSIBLE = "MEDICAL_UNIT_RESPONSIBLE"
    OTHER = "OTHER"


class IssueSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ArtifactType(StrEnum):
    ACTA_DOCX = "ACTA_DOCX"
    ANNEX_DOCX = "ANNEX_DOCX"
    EXCEL_XLSX = "EXCEL_XLSX"
    PROJECT_ZIP = "PROJECT_ZIP"
