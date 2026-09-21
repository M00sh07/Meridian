import pytest
import sys
import os
from datetime import datetime, timedelta

# Monorepo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
# apps/api root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from models import Repository, File, Commit, CommitFileChange, RepositoryStatus

client = TestClient(app)

NOW = datetime.utcnow()

_repo_a = None
_repo_empty = None
_repo_b = None
_files = {}

@pytest.fixture(scope="module", autouse=True)
def setup_db(isolated_application_engine, TestingSessionLocal):
    db = TestingSessionLocal()

    repo_a = Repository(url="https://github.com/test/hotspots-a", status=RepositoryStatus.completed)
    repo_empty = Repository(url="https://github.com/test/hotspots-empty", status=RepositoryStatus.completed)
    repo_b = Repository(url="https://github.com/test/hotspots-b", status=RepositoryStatus.completed)
    db.add_all([repo_a, repo_empty, repo_b])
    db.commit()

    global _repo_a, _repo_empty, _repo_b, _files
    _repo_a = repo_a.id
    _repo_empty = repo_empty.id
    _repo_b = repo_b.id

    f_hot = File(repository_id=_repo_a, path="src/hot.py", language="python")
    f_warm = File(repository_id=_repo_a, path="src/warm.py", language="python")
    f_cold = File(repository_id=_repo_a, path="src/cold.py", language="python")
    f_never = File(repository_id=_repo_a, path="src/never.py", language="python")
    f_b = File(repository_id=_repo_b, path="src/b.py", language="python")
    db.add_all([f_hot, f_warm, f_cold, f_never, f_b])
    db.commit()

    _files = {
        "hot": f_hot.id,
        "warm": f_warm.id,
        "cold": f_cold.id,
        "never": f_never.id,
        "b": f_b.id,
    }

    c_old = Commit(repository_id=_repo_a, sha="a-old", message="old", committed_at=NOW - timedelta(days=200))
    c_new = Commit(repository_id=_repo_a, sha="a-new", message="new", committed_at=NOW - timedelta(days=5))
    c_newer = Commit(repository_id=_repo_a, sha="a-newer", message="newer", committed_at=NOW - timedelta(days=1))
    c_b = Commit(repository_id=_repo_b, sha="b1", message="b1", committed_at=NOW)
    db.add_all([c_old, c_new, c_newer, c_b])
    db.commit()

    db.add_all([
        CommitFileChange(commit_id=c_old.id, file_id=_files["hot"], path="src/hot.py", change_type="modified"),
        CommitFileChange(commit_id=c_new.id, file_id=_files["hot"], path="src/hot.py", change_type="modified"),
        CommitFileChange(commit_id=c_newer.id, file_id=_files["hot"], path="src/hot.py", change_type="added"),
        CommitFileChange(commit_id=c_old.id, file_id=_files["warm"], path="src/warm.py", change_type="modified"),
        CommitFileChange(commit_id=c_new.id, file_id=_files["warm"], path="src/warm.py", change_type="modified"),
        CommitFileChange(commit_id=c_old.id, file_id=_files["cold"], path="src/cold.py", change_type="added"),
        CommitFileChange(commit_id=c_new.id, file_id=None, path="src/ghost.py", change_type="added"),
        CommitFileChange(commit_id=c_b.id, file_id=_files["b"], path="src/b.py", change_type="added"),
    ])
    db.commit()

    _commit_ids = [c_old.id, c_new.id, c_newer.id, c_b.id]
    db.close()

    yield

    db = TestingSessionLocal()
    db.query(CommitFileChange).filter(CommitFileChange.commit_id.in_(_commit_ids)).delete(synchronize_session=False)
    db.query(Commit).filter(Commit.id.in_(_commit_ids)).delete(synchronize_session=False)
    db.query(File).filter(File.id.in_(list(_files.values()))).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id.in_([_repo_a, _repo_empty, _repo_b])).delete(synchronize_session=False)
    db.commit()
    db.close()

def test_get_hotspots_success():
    response = client.get(f"/repositories/{_repo_a}/hotspots")
    assert response.status_code == 200
    data = response.json()

    assert [row["path"] for row in data] == ["src/hot.py", "src/warm.py", "src/cold.py"]

    hot, warm, cold = data
    assert hot["file_id"] == _files["hot"]
    assert hot["total_changes"] == 3
    assert hot["recent_changes"] == 2
    assert hot["last_changed_at"] is not None

    assert warm["file_id"] == _files["warm"]
    assert warm["total_changes"] == 2
    assert warm["recent_changes"] == 1

    assert cold["file_id"] == _files["cold"]
    assert cold["total_changes"] == 1
    assert cold["recent_changes"] == 0

    assert [row["total_changes"] for row in data] == [3, 2, 1]
    assert datetime.fromisoformat(hot["last_changed_at"]) > datetime.fromisoformat(warm["last_changed_at"])

def test_get_hotspots_excludes_other_repositories():
    response = client.get(f"/repositories/{_repo_a}/hotspots")
    assert response.status_code == 200
    paths = [row["path"] for row in response.json()]
    assert "src/b.py" not in paths
    assert "src/ghost.py" not in paths

def test_get_hotspots_empty_repository():
    response = client.get(f"/repositories/{_repo_empty}/hotspots")
    assert response.status_code == 200
    assert response.json() == []

def test_get_hotspots_limit():
    response = client.get(f"/repositories/{_repo_a}/hotspots?limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["file_id"] == _files["hot"]
    assert data[0]["total_changes"] == 3

def test_get_hotspots_limit_out_of_range():
    assert client.get(f"/repositories/{_repo_a}/hotspots?limit=101").status_code == 422
    assert client.get(f"/repositories/{_repo_a}/hotspots?limit=0").status_code == 422

def test_get_hotspots_unknown_repository():
    response = client.get("/repositories/999999/hotspots")
    assert response.status_code == 404
