import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import Repository, Commit, CommitFileChange, RepositoryStatus

client = TestClient(app)

def test_get_commit_changes_success():
    # Assuming repo_id=7 and a known commit SHA exists in DB
    # Based on prompt, repo 7 data is available.
    db = SessionLocal()
    repo = db.query(Repository).filter(Repository.id == 7).first()
    if repo:
        commit = db.query(Commit).filter(Commit.repository_id == repo.id).first()
        if commit:
            response = client.get(f"/repositories/{repo.id}/commits/{commit.sha}/changes")
            assert response.status_code == 200
            # A valid commit might return empty list or changes
            assert isinstance(response.json(), list)
            
    db.close()

def test_get_commit_changes_repo_404():
    response = client.get("/repositories/999/commits/some-sha/changes")
    assert response.status_code == 404

def test_get_commit_changes_commit_404():
    # Assuming repo 7 exists
    response = client.get("/repositories/7/commits/invalid-sha/changes")
    assert response.status_code == 404
