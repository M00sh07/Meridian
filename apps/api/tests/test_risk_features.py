import pytest
import os
from fastapi.testclient import TestClient
from datetime import datetime
from database import get_db
from models import File, Repository, Symbol, Dependency, Commit, CommitFileChange

# In-memory database setup specifically for isolated testing
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from main import app

test_db_path = os.path.join(os.path.dirname(__file__), "test_risk_features.db")
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
    
    repo = Repository(url="https://github.com/test/risk", status="completed", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(repo)
    repo2 = Repository(url="https://github.com/test/risk2", status="completed", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(repo2)
    db.commit()
    
    f1 = File(repository_id=repo.id, path="src/main.py")
    f2 = File(repository_id=repo.id, path="src/utils.py")
    f3 = File(repository_id=repo.id, path="src/core.py")
    f4 = File(repository_id=repo2.id, path="src/main.py")
    db.add_all([f1, f2, f3, f4])
    db.commit()
    
    # Symbols for f1 (3 total: 2 function, 1 class)
    s1 = Symbol(file_id=f1.id, name="main_func", type="function", signature="", start_line=1, end_line=10)
    s2 = Symbol(file_id=f1.id, name="helper", type="method", signature="", start_line=12, end_line=15)
    s3 = Symbol(file_id=f1.id, name="MyClass", type="class", signature="", start_line=20, end_line=30)
    db.add_all([s1, s2, s3])
    db.commit()
    
    # Dependencies (f1 -> f2, f3 -> f1)
    d1 = Dependency(source_file_id=f1.id, target_file_id=f2.id, imported_module="src.utils")
    d2 = Dependency(source_file_id=f3.id, target_file_id=f1.id, imported_module="src.main")
    db.add_all([d1, d2])
    db.commit()
    
    from datetime import timedelta
    now = datetime.utcnow()
    # c1: older than 30 days
    c1 = Commit(repository_id=repo.id, sha="hash1", author_name="A", message="msg1", committed_at=now - timedelta(days=40))
    # c2: recent
    c2 = Commit(repository_id=repo.id, sha="hash2", author_name="B", message="msg2", committed_at=now - timedelta(days=10))
    # c3: recent
    c3 = Commit(repository_id=repo.id, sha="hash3", author_name="B", message="msg3", committed_at=now - timedelta(days=5))
    db.add_all([c1, c2, c3])
    db.commit()
    
    cfc1 = CommitFileChange(commit_id=c1.id, file_id=f1.id, path="src/main.py", change_type="added")
    cfc2 = CommitFileChange(commit_id=c2.id, file_id=f1.id, path="src/main.py", change_type="modified")
    cfc3 = CommitFileChange(commit_id=c2.id, file_id=f2.id, path="src/utils.py", change_type="modified")
    cfc4 = CommitFileChange(commit_id=c3.id, file_id=f1.id, path="src/main.py", change_type="modified")
    db.add_all([cfc1, cfc2, cfc3, cfc4])
    db.commit()
    
    yield
    db.close()

def test_risk_features_success():
    response = client.get("/repositories/1/risk/features?path=src/main.py")
    assert response.status_code == 200
    data = response.json()
    
    # Check target
    assert data["target"]["path"] == "src/main.py"
    
    features = data["features"]
    # Structural features
    assert features["symbol_count"] == 3
    assert features["function_count"] == 2
    assert features["class_count"] == 1
    
    # Dependency features
    assert features["direct_dependency_count"] == 1
    assert features["direct_dependent_count"] == 1
    assert features["transitive_affected_file_count"] == 2 # f2 and f3
    
    # Historical features
    assert features["historical_change_count"] == 3 # c1, c2, c3
    assert features["recent_change_count"] == 2 # c2, c3
    assert features["co_changed_file_count"] == 1 # f2 (in c2)

def test_risk_features_missing_repo():
    response = client.get("/repositories/99/risk/features?path=src/main.py")
    assert response.status_code == 404

def test_risk_features_missing_file():
    response = client.get("/repositories/1/risk/features?path=missing.py")
    assert response.status_code == 404

def test_risk_features_normalization():
    response = client.get("/repositories/1/risk/features?path=src\\main.py")
    assert response.status_code == 200
    assert response.json()["target"]["path"] == "src/main.py"

def test_risk_features_repo_isolation():
    # f4 in repo 2 has no symbols, no deps, no commits
    response = client.get("/repositories/2/risk/features?path=src/main.py")
    assert response.status_code == 200
    features = response.json()["features"]
    assert features["symbol_count"] == 0
    assert features["direct_dependency_count"] == 0
    assert features["historical_change_count"] == 0

def test_risk_features_depth_behavior():
    # Test depth 0 (should use default 1 or handle gracefully if passed)
    # The API query bounds depth ge=1, le=10, so we pass 10
    response = client.get("/repositories/1/risk/features?path=src/main.py&depth=10")
    assert response.status_code == 200
    assert response.json()["features"]["transitive_affected_file_count"] == 2

