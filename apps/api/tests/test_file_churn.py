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
from models import Repository, File, Commit, CommitFileChange, RepositoryStatus

client = TestClient(app)

_repo_a = None
_repo_b = None
_file_a = None
_file_untouched = None
_file_b = None
_commit_a = None
_commit_b = None

@pytest.fixture(scope="module", autouse=True)
def setup_db(isolated_application_engine, TestingSessionLocal):
    db = TestingSessionLocal()

    repo_a = Repository(url="https://github.com/test/churn-a", status=RepositoryStatus.completed)
    repo_b = Repository(url="https://github.com/test/churn-b", status=RepositoryStatus.completed)
    db.add_all([repo_a, repo_b])
    db.commit()

    global _repo_a, _repo_b, _file_a, _file_untouched, _file_b, _commit_a, _commit_b
    _repo_a = repo_a.id
    _repo_b = repo_b.id

    f_a = File(repository_id=_repo_a, path="src/a.py", language="python")
    f_untouched = File(repository_id=_repo_a, path="src/untouched.py", language="python")
    f_b = File(repository_id=_repo_b, path="src/b.py", language="python")
    db.add_all([f_a, f_untouched, f_b])
    db.commit()
    _file_a = f_a.id
    _file_untouched = f_untouched.id
    _file_b = f_b.id

    c_a = Commit(repository_id=_repo_a, sha="a1", message="A1", committed_at=datetime(2026, 1, 1))
    c_b = Commit(repository_id=_repo_b, sha="b1", message="B1", committed_at=datetime(2026, 1, 2))
    db.add_all([c_a, c_b])
    db.commit()
    _commit_a = c_a.id
    _commit_b = c_b.id

    db.add_all([
        CommitFileChange(commit_id=_commit_a, file_id=_file_a, path="src/a.py", change_type="added"),
        CommitFileChange(commit_id=_commit_a, file_id=_file_a, path="src/a.py", change_type="added"),
        CommitFileChange(commit_id=_commit_a, file_id=_file_a, path="src/a.py", change_type="modified"),
        CommitFileChange(commit_id=_commit_a, file_id=_file_a, path="src/a.py", change_type="deleted"),
        CommitFileChange(commit_id=_commit_a, file_id=_file_a, path="src/a.py", change_type="renamed"),
        CommitFileChange(commit_id=_commit_b, file_id=_file_b, path="src/b.py", change_type="added"),
    ])
    db.commit()
    db.close()

    yield

    db = TestingSessionLocal()
    db.query(CommitFileChange).filter(CommitFileChange.commit_id.in_([_commit_a, _commit_b])).delete(synchronize_session=False)
    db.query(Commit).filter(Commit.id.in_([_commit_a, _commit_b])).delete(synchronize_session=False)
    db.query(File).filter(File.id.in_([_file_a, _file_untouched, _file_b])).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id.in_([_repo_a, _repo_b])).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_get_file_churn_success():
    response = client.get(f"/repositories/{_repo_a}/files/{_file_a}/churn")
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == _file_a
    assert data["path"] == "src/a.py"
    assert data["total_changes"] == 5
    assert data["added_count"] == 2
    assert data["modified_count"] == 1
    assert data["deleted_count"] == 1
    assert data["renamed_count"] == 1


def test_get_file_churn_zero_changes():
    response = client.get(f"/repositories/{_repo_a}/files/{_file_untouched}/churn")
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == _file_untouched
    assert data["path"] == "src/untouched.py"
    assert data["total_changes"] == 0
    assert data["added_count"] == 0
    assert data["modified_count"] == 0
    assert data["deleted_count"] == 0
    assert data["renamed_count"] == 0


def test_get_file_churn_wrong_repository():
    response = client.get(f"/repositories/{_repo_a}/files/{_file_b}/churn")
    assert response.status_code == 404


def test_get_file_churn_unknown_repository():
    response = client.get(f"/repositories/999999/files/{_file_a}/churn")
    assert response.status_code == 404
