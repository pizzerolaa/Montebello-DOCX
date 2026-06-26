from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.config import Settings
from app.models.project import Project


def create_project_zip(project: Project, settings: Settings, output_path: Path) -> Path:
    """Create a ZIP archive with all generated project artifacts except prior ZIP files."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", ZIP_DEFLATED) as archive:
        for artifact in project.generated_artifacts:
            if artifact.artifact_type == "PROJECT_ZIP":
                continue
            path = Path(artifact.stored_path)
            if path.exists():
                archive.write(path, arcname=artifact.filename)
    return output_path
