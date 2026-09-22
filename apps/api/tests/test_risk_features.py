"""Risk feature extraction tests.

Database isolation comes entirely from tests/conftest.py (`test_engine`,
`TestingSessionLocal` and the global `get_db` override). This module no longer
creates its own engine, never calls `drop_all()`, and never writes a .db file
next to the tests.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, UTC
from models import File, Repository, Symbol, Dependency, Commit, CommitFileChange
from main import app

client = TestClient(app)

# IDs captured during fixture setup (allocated by the database).
_repo_id = None
_repo2_id = None


@pytest.fixture(scope="module", autouse=True)
def populate_test_data(isolated_application_engine, TestingSessionLocal):
    """Create the rows this module needs in the isolated database."""
    db = TestingSessionLocal()
    global _repo_id, _repo2_id
    
    repo = Repository(url="https://github.com/test/risk", status="completed", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(repo)
    repo2 = Repository(url="https://github.com/test/risk2", status="completed", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(repo2)
    db.commit()
    
    _repo_id = repo.id
    _repo2_id = repo2.id
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
    now = datetime.now(UTC)
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
    response = client.get(f"/repositories/{_repo_id}/risk/features?path=src/main.py")
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

def test_risk_features_missing_repo(TestingSessionLocal):
    """An unknown repository id must 404; the id is derived, not hardcoded."""
    db = TestingSessionLocal()
    known_ids = {row.id for row in db.query(Repository.id).all()}
    db.close()

    unknown_id = max(known_ids) + 1 if known_ids else 1
    assert unknown_id not in known_ids
    response = client.get(f"/repositories/{unknown_id}/risk/features?path=src/main.py")
    assert response.status_code == 404

def test_risk_features_missing_file():
    response = client.get(f"/repositories/{_repo_id}/risk/features?path=missing.py")
    assert response.status_code == 404

def test_risk_features_normalization():
    response = client.get(f"/repositories/{_repo_id}/risk/features?path=src\\main.py")
    assert response.status_code == 200
    assert response.json()["target"]["path"] == "src/main.py"

def test_risk_features_repo_isolation():
    # f4 in repo 2 has no symbols, no deps, no commits
    response = client.get(f"/repositories/{_repo2_id}/risk/features?path=src/main.py")
    assert response.status_code == 200
    features = response.json()["features"]
    assert features["symbol_count"] == 0
    assert features["direct_dependency_count"] == 0
    assert features["historical_change_count"] == 0

def test_risk_features_depth_behavior():
    # Test depth 0 (should use default 1 or handle gracefully if passed)
    # The API query bounds depth ge=1, le=10, so we pass 10
    response = client.get(f"/repositories/{_repo_id}/risk/features?path=src/main.py&depth=10")
    assert response.status_code == 200
    assert response.json()["features"]["transitive_affected_file_count"] == 2

