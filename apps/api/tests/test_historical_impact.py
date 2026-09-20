import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from database import get_db
from models import File, Repository, Commit, CommitFileChange

# In-memory database setup specifically for isolated testing
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from main import app

import os
test_db_path = os.path.join(os.path.dirname(__file__), "test_hist.db")
engine = create_engine(
    f"sqlite:///{test_db_path}",
    connect_args={"check_same_thread": False},
)
Base.metadata.drop_all(bind=engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def populate_test_data():
    db = TestingSessionLocal()
    
    repo = Repository(url="https://github.com/test/hist", status="completed", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(repo)
    repo2 = Repository(url="https://github.com/test/other", status="completed", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(repo2)
    db.commit()
    
    f1 = File(repository_id=repo.id, path="src/main.py")
    f2 = File(repository_id=repo.id, path="src/utils.py")
    f3 = File(repository_id=repo.id, path="README.md")
    f4 = File(repository_id=repo2.id, path="src/main.py") # Isolated
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
    response = client.get("/repositories/1/history/impact?path=src/main.py")
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
    response = client.get("/repositories/1/history/impact?path=src/main.py&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["recent_commits"]) == 1
    assert data["recent_commits"][0]["sha"] == "hash3"
    # co-changes should also be limited
    assert len(data["co_changes"]) == 1
    assert data["co_changes"][0]["path"] == "src/utils.py"

def test_historical_impact_not_found_repo():
    response = client.get("/repositories/99/history/impact?path=src/main.py")
    assert response.status_code == 404

def test_historical_impact_not_found_file():
    response = client.get("/repositories/1/history/impact?path=missing.py")
    assert response.status_code == 404

def test_historical_impact_normalization():
    response = client.get("/repositories/1/history/impact?path=src\\main.py")
    assert response.status_code == 200
    data = response.json()
    assert data["target"]["path"] == "src/main.py"

def test_historical_impact_repo_isolation():
    response = client.get("/repositories/2/history/impact?path=src/main.py")
    assert response.status_code == 200
    data = response.json()
    assert data["total_changes"] == 0
    assert data["co_changes"] == []
