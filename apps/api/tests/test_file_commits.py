import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import Repository, File

client = TestClient(app)

def test_get_file_commits_success():
    db = SessionLocal()
    # Find a repo and a file that has changes
    repo = db.query(Repository).first()
    if repo:
        file = db.query(File).filter(File.repository_id == repo.id).first()
        if file:
            response = client.get(f"/repositories/{repo.id}/files/{file.id}/commits")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert isinstance(data["items"], list)
    db.close()

def test_get_file_commits_pagination():
    db = SessionLocal()
    repo = db.query(Repository).first()
    if repo:
        file = db.query(File).filter(File.repository_id == repo.id).first()
        if file:
            response = client.get(f"/repositories/{repo.id}/files/{file.id}/commits?page=1&limit=1")
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) <= 1
    db.close()

def test_get_file_commits_404_repo():
    response = client.get("/repositories/9999/files/1/commits")
    assert response.status_code == 404

def test_get_file_commits_404_file():
    db = SessionLocal()
    repo = db.query(Repository).first()
    if repo:
        # File id that doesn't exist
        response = client.get(f"/repositories/{repo.id}/files/99999/commits")
        assert response.status_code == 404
    db.close()
