import pytest
import sys
import os

# Monorepo root for services.*
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
# apps/api root for main, database, models, etc.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.ingestion.git_service import validate_github_url
from services.parser.tree_sitter_service import detect_language
from fastapi.testclient import TestClient
from main import app
from database import Base, engine

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_validate_github_url():
    assert validate_github_url("https://github.com/owner/repo") is True
    assert validate_github_url("http://github.com/owner/repo") is False
    assert validate_github_url("https://gitlab.com/owner/repo") is False

def test_detect_language():
    assert detect_language("test.py") == "python"
    assert detect_language("test.js") == "javascript"
    assert detect_language("test.ts") == "typescript"
    assert detect_language("test.txt") is None

client = TestClient(app)

def test_api_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_api_create_repository_invalid_url():
    response = client.post("/repositories/", json={"url": "https://gitlab.com/test/repo"})
    assert response.status_code == 400

def test_api_create_repository_valid_url():
    # Will fail git clone in background but API should return 200 pending
    response = client.post("/repositories/", json={"url": "https://github.com/test/repo"})
    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "https://github.com/test/repo"
    assert data["status"] == "pending"
    assert "id" in data
