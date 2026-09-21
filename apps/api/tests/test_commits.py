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
from models import Repository, Commit, RepositoryStatus

client = TestClient(app)
_repo_id = None
_commit_ids = []


@pytest.fixture(scope="module", autouse=True)
def setup_db(isolated_application_engine, TestingSessionLocal):
    db = TestingSessionLocal()

    repo = Repository(url="https://github.com/test/repo6", status=RepositoryStatus.completed)
    db.add(repo)
    db.commit()

    global _repo_id, _commit_ids
    _repo_id = repo.id

    for i in range(1, 7):
        commit = Commit(
            repository_id=_repo_id,
            sha=f"sha{i}",
            author_name=f"Author {i}",
            author_email=f"author{i}@example.com",
            message=f"Commit {i}",
            committed_at=datetime(2026, 9, 19, 10, i, 0)
        )
        db.add(commit)
    db.commit()

    _commit_ids = [c.id for c in db.query(Commit).filter_by(repository_id=_repo_id).all()]
    db.close()

    yield

    db = TestingSessionLocal()
    db.query(Commit).filter(Commit.id.in_(_commit_ids)).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id == _repo_id).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_get_commits_success():
    response = client.get(f"/repositories/{_repo_id}/commits")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 6
    assert data["total"] == 6
    # Check newest first order
    assert data["items"][0]["message"] == "Commit 6"
    assert data["items"][5]["message"] == "Commit 1"

def test_get_commits_pagination():
    response = client.get(f"/repositories/{_repo_id}/commits?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 6
    assert data["items"][0]["message"] == "Commit 6"
    assert data["items"][1]["message"] == "Commit 5"

def test_get_commits_404():
    response = client.get("/repositories/999999/commits")
    assert response.status_code == 404
