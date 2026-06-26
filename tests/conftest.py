from __future__ import annotations

import importlib
import shutil
import sys
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def make_docx_bytes(text: str = "REPORTE DE TRABAJO") -> bytes:
    buffer = BytesIO()
    document = Document()
    for line in text.splitlines() or [text]:
        document.add_paragraph(line)
    document.save(buffer)
    return buffer.getvalue()


@pytest.fixture()
def workspace_tmp_path() -> Path:
    root = PROJECT_ROOT / "storage" / "test_runs" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture()
def isolated_client(workspace_tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("AUTH_ENABLED", "false")

    import app.config as config

    config.get_settings.cache_clear()

    import app.main as main
    from app import models  # noqa: F401
    from app.config import Settings, get_settings
    from app.database import Base, get_db
    from app.routes.projects import get_db as projects_get_db
    from app.routes.uploads import get_db as uploads_get_db

    main = importlib.reload(main)
    database_url = f"sqlite:///{workspace_tmp_path / 'app.db'}"
    storage_root = workspace_tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    settings = Settings(database_url=database_url, storage_root=storage_root)
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_settings() -> Settings:
        return settings

    main.app.dependency_overrides[get_db] = override_get_db
    main.app.dependency_overrides[projects_get_db] = override_get_db
    main.app.dependency_overrides[uploads_get_db] = override_get_db
    main.app.dependency_overrides[get_settings] = override_settings

    with TestClient(main.app) as client:
        yield client

    main.app.dependency_overrides.clear()
