import pytest
from fastapi.testclient import TestClient
from main import app
from models import Repository, File, Commit, CommitFileChange, RepositoryStatus
from datetime import datetime

client = TestClient(app)

_repo_id = None
_file_id = None
_commit_id = None

@pytest.fixture(scope="module", autouse=True)
def setup_file_commits_data(isolated_application_engine, TestingSessionLocal):
    db = TestingSessionLocal()
    repo = Repository(url="https://github.com/test/fc-repo", status=RepositoryStatus.completed)
    db.add(repo)
    db.commit()
    global _repo_id, _file_id, _commit_id
    _repo_id = repo.id

    file = File(repository_id=_repo_id, path="src/main.py", language="python")
    db.add(file)
    db.commit()
    _file_id = file.id

    commit = Commit(repository_id=_repo_id, sha="fc-sha1", message="First commit",
                    committed_at=datetime(2026, 1, 1))
    db.add(commit)
    db.commit()
    _commit_id = commit.id

    db.add(CommitFileChange(commit_id=_commit_id, file_id=_file_id, path="src/main.py", change_type="added"))
    db.commit()
    db.close()

    yield

    db = TestingSessionLocal()
    db.query(CommitFileChange).filter(CommitFileChange.commit_id == _commit_id).delete(synchronize_session=False)
    db.query(Commit).filter(Commit.id == _commit_id).delete(synchronize_session=False)
    db.query(File).filter(File.id == _file_id).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id == _repo_id).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_get_file_commits_success():
    response = client.get(f"/repositories/{_repo_id}/files/{_file_id}/commits")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) == 1


def test_get_file_commits_pagination():
    response = client.get(f"/repositories/{_repo_id}/files/{_file_id}/commits?page=1&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 1


def test_get_file_commits_404_repo():
    response = client.get(f"/repositories/999999/files/{_file_id}/commits")
    assert response.status_code == 404


def test_get_file_commits_404_file():
    response = client.get(f"/repositories/{_repo_id}/files/999999/commits")
    assert response.status_code == 404
