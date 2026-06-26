from __future__ import annotations

from app.models.enums import ProjectStatus
from app.models.extraction_issue import ExtractionIssue
from app.models.project import Project


REQUIRED_PROJECT_FIELDS = ["center_name", "order_number", "service_date_raw"]


def update_project_review_status(project: Project) -> None:
    """Update project status after manual review edits."""
    blocking = [issue for issue in project.extraction_issues if issue.severity == "ERROR" and not issue.resolved]
    missing = [field for field in REQUIRED_PROJECT_FIELDS if not getattr(project, field)]
    if blocking or missing or not project.equipment:
        project.status = ProjectStatus.NEEDS_REVIEW.value
        return
    project.status = ProjectStatus.READY.value


def resolve_field_issues(project: Project, entity_type: str, field_names: set[str]) -> None:
    """Resolve issues for fields that were manually supplied by the reviewer."""
    for issue in project.extraction_issues:
        if issue.entity_type == entity_type and issue.field_name in field_names:
            issue.resolved = True
            if issue.resolved_value is None:
                issue.resolved_value = "Revisado manualmente"


def unresolved_issues(project: Project) -> list[ExtractionIssue]:
    return [issue for issue in project.extraction_issues if not issue.resolved]

