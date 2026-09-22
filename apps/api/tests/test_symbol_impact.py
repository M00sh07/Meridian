"""Symbol impact tests.

Database isolation comes entirely from tests/conftest.py (`test_engine`,
`TestingSessionLocal` and the global `get_db` override). This module no longer
creates its own engine, never calls `drop_all()`, and never writes a .db file
next to the tests.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, UTC
from models import File, Repository, Symbol, Dependency
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

    repo = Repository(url="https://github.com/test/sym", status="completed", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(repo)
    repo2 = Repository(url="https://github.com/test/iso", status="completed", created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(repo2)
    db.commit()

    _repo_id = repo.id
    _repo2_id = repo2.id

    # f1 -> f2 -> f3 cycle: f3 -> f1
    f1 = File(repository_id=repo.id, path="src/main.py")
    f2 = File(repository_id=repo.id, path="src/utils.py")
    f3 = File(repository_id=repo.id, path="src/core.py")
    f4 = File(repository_id=repo2.id, path="src/main.py")  # isolated
    db.add_all([f1, f2, f3, f4])
    db.commit()

    s1 = Symbol(file_id=f1.id, name="main_func", type="function", signature="def main()", start_line=1, end_line=10)
    s2 = Symbol(file_id=f1.id, name="helper", type="function", signature="def helper()", start_line=12, end_line=15)
    s3 = Symbol(file_id=f4.id, name="main_func", type="function", signature="def main()", start_line=1, end_line=10)
    db.add_all([s1, s2, s3])
    db.commit()

    d1 = Dependency(source_file_id=f1.id, target_file_id=f2.id, imported_module="src.utils")
    d2 = Dependency(source_file_id=f2.id, target_file_id=f3.id, imported_module="src.core")
    d3 = Dependency(source_file_id=f3.id, target_file_id=f1.id, imported_module="src.main")
    db.add_all([d1, d2, d3])
    db.commit()

    yield
    db.close()

def test_symbol_impact_success():
    response = client.get(f"/repositories/{_repo_id}/impact/symbol?path=src/main.py&symbol=main_func&depth=2")
    assert response.status_code == 200
    data = response.json()

    assert data["target_symbol"]["path"] == "src/main.py"
    assert data["target_symbol"]["symbol_name"] == "main_func"
    assert data["target_symbol"]["symbol_type"] == "function"
    assert data["target_symbol"]["start_line"] == 1

    assert len(data["file_level_direct_dependencies"]) == 1
    assert data["file_level_direct_dependencies"][0]["path"] == "src/utils.py"

    assert len(data["file_level_direct_dependents"]) == 1
    assert data["file_level_direct_dependents"][0]["path"] == "src/core.py"

    assert data["file_level_total_affected"] == 2

def test_symbol_impact_not_found_repo(TestingSessionLocal):
    """An unknown repository id must 404; the id is derived, not hardcoded."""
    db = TestingSessionLocal()
    known_ids = {row.id for row in db.query(Repository.id).all()}
    db.close()

    unknown_id = max(known_ids) + 1 if known_ids else 1
    assert unknown_id not in known_ids
    response = client.get(f"/repositories/{unknown_id}/impact/symbol?path=src/main.py&symbol=main_func")
    assert response.status_code == 404

def test_symbol_impact_not_found_file():
    response = client.get(f"/repositories/{_repo_id}/impact/symbol?path=missing.py&symbol=main_func")
    assert response.status_code == 404

def test_symbol_impact_not_found_symbol():
    response = client.get(f"/repositories/{_repo_id}/impact/symbol?path=src/main.py&symbol=missing")
    assert response.status_code == 404

def test_symbol_impact_normalization():
    response = client.get(f"/repositories/{_repo_id}/impact/symbol?path=src\\main.py&symbol=main_func")
    assert response.status_code == 200
    assert response.json()["target_symbol"]["path"] == "src/main.py"

def test_symbol_impact_repo_isolation():
    response = client.get(f"/repositories/{_repo2_id}/impact/symbol?path=src/main.py&symbol=main_func")
    assert response.status_code == 200
    assert response.json()["file_level_total_affected"] == 0
