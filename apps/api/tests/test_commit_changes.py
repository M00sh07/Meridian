import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from main import app
from models import Repository, Commit, CommitFileChange, RepositoryStatus

client = TestClient(app)

_repo_id = None
_commit_id = None
COMMIT_SHA = "cc-sha1"

@pytest.fixture(scope="module", autouse=True)
def setup_commit_changes_data(isolated_application_engine, TestingSessionLocal):
    db = TestingSessionLocal()
    repo = Repository(url="https://github.com/test/cc-repo", status=RepositoryStatus.completed)
    db.add(repo)
    db.commit()
    global _repo_id, _commit_id
    _repo_id = repo.id

    commit = Commit(repository_id=_repo_id, sha=COMMIT_SHA, message="First",
                    committed_at=datetime(2026, 1, 1))
    db.add(commit)
    db.commit()
    _commit_id = commit.id

    db.add(CommitFileChange(commit_id=_commit_id, file_id=None, path="src/main.py", change_type="added"))
    db.commit()
    db.close()

    yield

    db = TestingSessionLocal()
    db.query(CommitFileChange).filter(CommitFileChange.commit_id == _commit_id).delete(synchronize_session=False)
    db.query(Commit).filter(Commit.id == _commit_id).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id == _repo_id).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_get_commit_changes_success():
    response = client.get(f"/repositories/{_repo_id}/commits/{COMMIT_SHA}/changes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_commit_changes_repo_404():
    response = client.get(f"/repositories/999999/commits/{COMMIT_SHA}/changes")
    assert response.status_code == 404


def test_get_commit_changes_commit_404():
    response = client.get(f"/repositories/{_repo_id}/commits/invalid-sha/changes")
    assert response.status_code == 404
