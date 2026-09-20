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
from models import Repository, File, Commit, CommitFileChange, RepositoryStatus

REPO_A = 8001
REPO_B = 8002


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    db.add(Repository(id=REPO_A, url="https://github.com/test/churn-a", status=RepositoryStatus.completed))
    db.add(Repository(id=REPO_B, url="https://github.com/test/churn-b", status=RepositoryStatus.completed))

    # Files in repo A (one with changes, one with none) and one in repo B
    db.add(File(id=8001, repository_id=REPO_A, path="src/a.py", language="python"))
    db.add(File(id=8002, repository_id=REPO_A, path="src/untouched.py", language="python"))
    db.add(File(id=8003, repository_id=REPO_B, path="src/b.py", language="python"))
    db.commit()

    # Commits: one in repo A, one in repo B
    db.add(Commit(id=8001, repository_id=REPO_A, sha="a1", message="A1", committed_at=datetime(2026, 1, 1)))
    db.add(Commit(id=8002, repository_id=REPO_B, sha="b1", message="B1", committed_at=datetime(2026, 1, 2)))
    db.commit()

    # Changes for file 8001 in repo A: 2 added, 1 modified, 1 deleted, 1 renamed
    db.add(CommitFileChange(commit_id=8001, file_id=8001, path="src/a.py", change_type="added"))
    db.add(CommitFileChange(commit_id=8001, file_id=8001, path="src/a.py", change_type="added"))
    db.add(CommitFileChange(commit_id=8001, file_id=8001, path="src/a.py", change_type="modified"))
    db.add(CommitFileChange(commit_id=8001, file_id=8001, path="src/a.py", change_type="deleted"))
    db.add(CommitFileChange(commit_id=8001, file_id=8001, path="src/a.py", change_type="renamed"))
    # Unrelated change in repo B that must never affect repo A counts
    db.add(CommitFileChange(commit_id=8002, file_id=8003, path="src/b.py", change_type="added"))
    db.commit()
    db.close()

    yield

    db = SessionLocal()
    db.query(CommitFileChange).filter(CommitFileChange.commit_id.in_([8001, 8002])).delete(synchronize_session=False)
    db.query(Commit).filter(Commit.repository_id.in_([REPO_A, REPO_B])).delete(synchronize_session=False)
    db.query(File).filter(File.repository_id.in_([REPO_A, REPO_B])).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id.in_([REPO_A, REPO_B])).delete(synchronize_session=False)
    db.commit()
    db.close()


client = TestClient(app)


def test_get_file_churn_success():
    response = client.get(f"/repositories/{REPO_A}/files/8001/churn")
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == 8001
    assert data["path"] == "src/a.py"
    assert data["total_changes"] == 5
    assert data["added_count"] == 2
    assert data["modified_count"] == 1
    assert data["deleted_count"] == 1
    assert data["renamed_count"] == 1


def test_get_file_churn_zero_changes():
    response = client.get(f"/repositories/{REPO_A}/files/8002/churn")
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == 8002
    assert data["path"] == "src/untouched.py"
    assert data["total_changes"] == 0
    assert data["added_count"] == 0
    assert data["modified_count"] == 0
    assert data["deleted_count"] == 0
    assert data["renamed_count"] == 0


def test_get_file_churn_wrong_repository():
    # File 8003 belongs to repo B, requested under repo A
    response = client.get(f"/repositories/{REPO_A}/files/8003/churn")
    assert response.status_code == 404


def test_get_file_churn_unknown_repository():
    response = client.get("/repositories/9999/files/8001/churn")
    assert response.status_code == 404
