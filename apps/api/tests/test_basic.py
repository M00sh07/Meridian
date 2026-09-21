"""Health/validation tests.

Database isolation comes from tests/conftest.py: the FastAPI `get_db`
dependency is overridden to the temporary SQLite engine for every test, so
nothing here can touch apps/api/meredian.db.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ingestion_job import is_safe_github_url, detect_language
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _get_session():
    """Open a session on the isolated test database (see tests/conftest.py)."""
    from database import SessionLocal
    return SessionLocal()


def test_validate_github_url():
    assert is_safe_github_url("https://github.com/owner/repo") is True
    assert is_safe_github_url("http://github.com/owner/repo") is False
    assert is_safe_github_url("https://gitlab.com/owner/repo") is False


def test_detect_language():
    assert detect_language("test.py") == "python"
    assert detect_language("test.js") == "javascript"
    assert detect_language("test.ts") == "typescript"
    assert detect_language("test.txt") is None


def test_api_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_create_repository_invalid_url():
    response = client.post("/repositories/", json={"url": "https://gitlab.com/test/repo"})
    assert response.status_code == 400


def test_api_create_repository_valid_url():
    """A valid URL is accepted and stored as pending.

    The background ingestion task is never awaited by TestClient, so no clone
    and no ingestion write happens during this test.
    """
    response = client.post("/repositories/", json={"url": "https://github.com/test/repo"})
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://github.com/test/repo"
    assert data["status"] == "pending"
    assert "id" in data


def test_prepare_for_ingestion_refuses_non_github_urls():
    """Ingestion must reject unsafe remote URLs before any clone work."""
    from models import Repository, RepositoryStatus
    from services.ingestion_job import _prepare_for_ingestion

    db = _get_session()
    repo = Repository(url="https://gitlab.com/test/repo", status=RepositoryStatus.pending)
    db.add(repo)
    db.commit()
    repo_id = repo.id
    db.close()

    assert _prepare_for_ingestion(repo_id) is None
    # An unknown repository id is rejected rather than raising.
    assert _prepare_for_ingestion(repo_id + 10 ** 9) is None


def test_prepare_for_ingestion_allows_local_file_urls():
    """Local file:/// ingestion paths must stay usable for development."""
    from models import Repository, RepositoryStatus
    from services.ingestion_job import _prepare_for_ingestion

    db = _get_session()
    repo = Repository(url="file:///tmp/example", status=RepositoryStatus.pending)
    db.add(repo)
    db.commit()
    repo_id = repo.id
    db.close()

    assert _prepare_for_ingestion(repo_id) == "file:///tmp/example"
