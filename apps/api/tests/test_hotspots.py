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
from database import Base, engine, SessionLocal
from models import Repository, File, Commit, CommitFileChange, RepositoryStatus

REPO_A = 8101
REPO_EMPTY = 8102
REPO_B = 8103

NOW = datetime.utcnow()


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    db.add(Repository(id=REPO_A, url="https://github.com/test/hotspots-a", status=RepositoryStatus.completed))
    db.add(Repository(id=REPO_EMPTY, url="https://github.com/test/hotspots-empty", status=RepositoryStatus.completed))
    db.add(Repository(id=REPO_B, url="https://github.com/test/hotspots-b", status=RepositoryStatus.completed))

    # Repo A files
    db.add(File(id=8101, repository_id=REPO_A, path="src/hot.py", language="python"))
    db.add(File(id=8102, repository_id=REPO_A, path="src/warm.py", language="python"))
    db.add(File(id=8103, repository_id=REPO_A, path="src/cold.py", language="python"))
    db.add(File(id=8104, repository_id=REPO_A, path="src/never.py", language="python"))
    # Repo B file, must never appear in repo A results
    db.add(File(id=8105, repository_id=REPO_B, path="src/b.py", language="python"))
    db.commit()

    # Repo A commits: old (outside 90d window) and recent (inside window)
    db.add(Commit(id=8101, repository_id=REPO_A, sha="a-old", message="old",
                  committed_at=NOW - timedelta(days=200)))
    db.add(Commit(id=8102, repository_id=REPO_A, sha="a-new", message="new",
                  committed_at=NOW - timedelta(days=5)))
    db.add(Commit(id=8103, repository_id=REPO_A, sha="a-newer", message="newer",
                  committed_at=NOW - timedelta(days=1)))
    # Repo B commit
    db.add(Commit(id=8104, repository_id=REPO_B, sha="b1", message="b1", committed_at=NOW))
    db.commit()

    # src/hot.py: 3 changes (1 old, 2 recent), latest = 1 day ago
    db.add(CommitFileChange(commit_id=8101, file_id=8101, path="src/hot.py", change_type="modified"))
    db.add(CommitFileChange(commit_id=8102, file_id=8101, path="src/hot.py", change_type="modified"))
    db.add(CommitFileChange(commit_id=8103, file_id=8101, path="src/hot.py", change_type="added"))
    # src/warm.py: 2 changes (1 old, 1 recent), latest = 5 days ago
    db.add(CommitFileChange(commit_id=8101, file_id=8102, path="src/warm.py", change_type="modified"))
    db.add(CommitFileChange(commit_id=8102, file_id=8102, path="src/warm.py", change_type="modified"))
    # src/cold.py: 1 old change only -> 0 recent
    db.add(CommitFileChange(commit_id=8101, file_id=8103, path="src/cold.py", change_type="added"))
    # src/never.py has no changes at all -> must be absent
    # Unmapped change (file_id NULL) must be ignored entirely
    db.add(CommitFileChange(commit_id=8102, file_id=None, path="src/ghost.py", change_type="added"))
    # Repo B change to its own file
    db.add(CommitFileChange(commit_id=8104, file_id=8105, path="src/b.py", change_type="added"))
    db.commit()
    db.close()

    yield

    db = SessionLocal()
    db.query(CommitFileChange).filter(CommitFileChange.path.in_(
        ["src/hot.py", "src/warm.py", "src/cold.py", "src/ghost.py", "src/b.py"]
    )).delete(synchronize_session=False)
    db.query(Commit).filter(Commit.repository_id.in_([REPO_A, REPO_EMPTY, REPO_B])).delete(synchronize_session=False)
    db.query(File).filter(File.repository_id.in_([REPO_A, REPO_EMPTY, REPO_B])).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id.in_([REPO_A, REPO_EMPTY, REPO_B])).delete(synchronize_session=False)
    db.commit()
    db.close()


client = TestClient(app)


def test_get_hotspots_success():
    response = client.get(f"/repositories/{REPO_A}/hotspots")
    assert response.status_code == 200
    data = response.json()

    # Only files with mapped changes appear; never-changed files are excluded
    assert [row["path"] for row in data] == ["src/hot.py", "src/warm.py", "src/cold.py"]

    hot, warm, cold = data
    assert hot["file_id"] == 8101
    assert hot["total_changes"] == 3
    assert hot["recent_changes"] == 2
    assert hot["last_changed_at"] is not None

    assert warm["file_id"] == 8102
    assert warm["total_changes"] == 2
    assert warm["recent_changes"] == 1

    # Old-only change: counted in total, zero recent
    assert cold["file_id"] == 8103
    assert cold["total_changes"] == 1
    assert cold["recent_changes"] == 0

    # Ordering: total_changes desc
    assert [row["total_changes"] for row in data] == [3, 2, 1]
    # last_changed_at is the max commit timestamp per file
    assert datetime.fromisoformat(hot["last_changed_at"]) > datetime.fromisoformat(warm["last_changed_at"])


def test_get_hotspots_excludes_other_repositories():
    response = client.get(f"/repositories/{REPO_A}/hotspots")
    assert response.status_code == 200
    paths = [row["path"] for row in response.json()]
    assert "src/b.py" not in paths
    assert "src/ghost.py" not in paths


def test_get_hotspots_empty_repository():
    response = client.get(f"/repositories/{REPO_EMPTY}/hotspots")
    assert response.status_code == 200
    assert response.json() == []


def test_get_hotspots_limit():
    response = client.get(f"/repositories/{REPO_A}/hotspots?limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["file_id"] == 8101
    assert data[0]["total_changes"] == 3


def test_get_hotspots_limit_out_of_range():
    # Maximum is 100
    assert client.get(f"/repositories/{REPO_A}/hotspots?limit=101").status_code == 422
    # Minimum is 1
    assert client.get(f"/repositories/{REPO_A}/hotspots?limit=0").status_code == 422


def test_get_hotspots_unknown_repository():
    response = client.get("/repositories/9999/hotspots")
    assert response.status_code == 404
