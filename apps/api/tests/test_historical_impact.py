"""Historical impact tests.

Database isolation comes entirely from tests/conftest.py (`test_engine`,
`TestingSessionLocal` and the global `get_db` override). This module no longer
creates its own engine, never calls `drop_all()`, and never writes a .db file
next to the tests.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, UTC
from models import File, Repository, Commit, CommitFileChange
from main import app

client = TestClient(app)

# IDs captured during fixture setup (allocated by the database).
_repo_id = None
_repo2_id = None


@pytest.fixture(scope="module", autouse=True)
def populate_test_data(isolated_application_engine, TestingSessionLocal):
    """Create the rows this module needs inside the shared temporary database."""
    global _repo_id, _repo2_id
    db = TestingSessionLocal()

    repo = Repository(url="https://github.com/test/hist", status="completed", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(repo)
    repo2 = Repository(url="https://github.com/test/other", status="completed", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(repo2)
    db.commit()

    _repo_id = repo.id
    _repo2_id = repo2.id

    f1 = File(repository_id=repo.id, path="src/main.py")
    f2 = File(repository_id=repo.id, path="src/utils.py")
    f3 = File(repository_id=repo.id, path="README.md")
    f4 = File(repository_id=repo2.id, path="src/main.py")  # Isolated
    db.add_all([f1, f2, f3, f4])
    db.commit()

    # Commit 1 touches f1 and f2
    c1 = Commit(repository_id=repo.id, sha="hash1", author_name="A", message="msg1", committed_at=datetime(2023, 1, 1))
    # Commit 2 touches f1 and f3
    c2 = Commit(repository_id=repo.id, sha="hash2", author_name="A", message="msg2", committed_at=datetime(2023, 1, 2))
    # Commit 3 touches f1 and f2 again
    c3 = Commit(repository_id=repo.id, sha="hash3", author_name="B", message="msg3", committed_at=datetime(2023, 1, 3))

    db.add_all([c1, c2, c3])
    db.commit()

    cfc1_1 = CommitFileChange(commit_id=c1.id, file_id=f1.id, path="src/main.py", change_type="added")
    cfc1_2 = CommitFileChange(commit_id=c1.id, file_id=f2.id, path="src/utils.py", change_type="added")

    cfc2_1 = CommitFileChange(commit_id=c2.id, file_id=f1.id, path="src/main.py", change_type="modified")
    cfc2_3 = CommitFileChange(commit_id=c2.id, file_id=f3.id, path="README.md", change_type="added")

    cfc3_1 = CommitFileChange(commit_id=c3.id, file_id=f1.id, path="src/main.py", change_type="modified")
    cfc3_2 = CommitFileChange(commit_id=c3.id, file_id=f2.id, path="src/utils.py", change_type="modified")

    db.add_all([cfc1_1, cfc1_2, cfc2_1, cfc2_3, cfc3_1, cfc3_2])
    db.commit()

    yield
    db.close()

def test_historical_impact_success():
    response = client.get(f"/repositories/{_repo_id}/history/impact?path=src/main.py")
    assert response.status_code == 200
    data = response.json()
    assert data["target"]["path"] == "src/main.py"
    assert data["total_changes"] == 3
    assert data["first_commit_date"] == "2023-01-01T00:00:00"
    assert data["last_commit_date"] == "2023-01-03T00:00:00"

    # Recent commits sorted descending
    assert len(data["recent_commits"]) == 3
    assert data["recent_commits"][0]["sha"] == "hash3"
    assert data["recent_commits"][1]["sha"] == "hash2"
    assert data["recent_commits"][2]["sha"] == "hash1"

    # Co-changes
    # f1 shares c1, c3 with f2 (2 shared)
    # f1 shares c2 with f3 (1 shared)
    assert len(data["co_changes"]) == 2
    assert data["co_changes"][0]["path"] == "src/utils.py"
    assert data["co_changes"][0]["shared_commits"] == 2
    assert data["co_changes"][1]["path"] == "README.md"
    assert data["co_changes"][1]["shared_commits"] == 1

def test_historical_impact_limit():
    response = client.get(f"/repositories/{_repo_id}/history/impact?path=src/main.py&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["recent_commits"]) == 1
    assert data["recent_commits"][0]["sha"] == "hash3"
    # co-changes should also be limited
    assert len(data["co_changes"]) == 1
    assert data["co_changes"][0]["path"] == "src/utils.py"

def test_historical_impact_not_found_repo(TestingSessionLocal):
    """An unknown repository id must 404; the id is derived, not hardcoded."""
    db = TestingSessionLocal()
    known_ids = {row.id for row in db.query(Repository.id).all()}
    db.close()

    unknown_id = max(known_ids) + 1 if known_ids else 1
    assert unknown_id not in known_ids
    response = client.get(f"/repositories/{unknown_id}/history/impact?path=src/main.py")
    assert response.status_code == 404

def test_historical_impact_not_found_file():
    response = client.get(f"/repositories/{_repo_id}/history/impact?path=missing.py")
    assert response.status_code == 404

def test_historical_impact_normalization():
    response = client.get(f"/repositories/{_repo_id}/history/impact?path=src\\main.py")
    assert response.status_code == 200
    data = response.json()
    assert data["target"]["path"] == "src/main.py"

def test_historical_impact_repo_isolation():
    response = client.get(f"/repositories/{_repo2_id}/history/impact?path=src/main.py")
    assert response.status_code == 200
    data = response.json()
    assert data["total_changes"] == 0
    assert data["co_changes"] == []
