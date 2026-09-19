import pytest
import sys
import os
from datetime import datetime

# Monorepo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
# apps/api root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from database import Base, engine, SessionLocal
from models import Repository, Commit, RepositoryStatus

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Create Repo 6
    repo = Repository(id=6, url="https://github.com/test/repo6", status=RepositoryStatus.completed)
    db.add(repo)
    db.commit()
    
    # Create 6 Commits for Repo 6
    for i in range(1, 7):
        commit = Commit(
            repository_id=6,
            sha=f"sha{i}",
            author_name=f"Author {i}",
            author_email=f"author{i}@example.com",
            message=f"Commit {i}",
            committed_at=datetime(2026, 9, 19, 10, i, 0)
        )
        db.add(commit)
    db.commit()
    db.close()
    
    yield
    
    db = SessionLocal()
    db.query(Commit).filter(Commit.repository_id == 6).delete()
    db.query(Repository).filter(Repository.id == 6).delete()
    db.commit()
    db.close()

client = TestClient(app)

def test_get_commits_success():
    response = client.get("/repositories/6/commits")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 6
    assert data["total"] == 6
    # Check newest first order
    assert data["items"][0]["message"] == "Commit 6"
    assert data["items"][5]["message"] == "Commit 1"

def test_get_commits_pagination():
    response = client.get("/repositories/6/commits?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 6
    assert data["items"][0]["message"] == "Commit 6"
    assert data["items"][1]["message"] == "Commit 5"

def test_get_commits_404():
    response = client.get("/repositories/999/commits")
    assert response.status_code == 404
