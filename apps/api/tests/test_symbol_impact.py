import pytest
import os
from fastapi.testclient import TestClient
from datetime import datetime
from database import get_db
from models import File, Repository, Symbol, Dependency

# In-memory database setup specifically for isolated testing
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from main import app

test_db_path = os.path.join(os.path.dirname(__file__), "test_symbol.db")
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
    
    repo = Repository(url="https://github.com/test/sym", status="completed", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(repo)
    repo2 = Repository(url="https://github.com/test/iso", status="completed", created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(repo2)
    db.commit()
    
    # f1 -> f2 -> f3 cycle: f3 -> f1
    f1 = File(repository_id=repo.id, path="src/main.py")
    f2 = File(repository_id=repo.id, path="src/utils.py")
    f3 = File(repository_id=repo.id, path="src/core.py")
    f4 = File(repository_id=repo2.id, path="src/main.py") # isolated
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
    response = client.get("/repositories/1/impact/symbol?path=src/main.py&symbol=main_func&depth=2")
    assert response.status_code == 200
    data = response.json()
    
    # Check target
    assert data["target_symbol"]["path"] == "src/main.py"
    assert data["target_symbol"]["symbol_name"] == "main_func"
    assert data["target_symbol"]["symbol_type"] == "function"
    assert data["target_symbol"]["start_line"] == 1
    
    # Check dependencies (file level impact)
    assert len(data["file_level_direct_dependencies"]) == 1
    assert data["file_level_direct_dependencies"][0]["path"] == "src/utils.py"
    
    assert len(data["file_level_direct_dependents"]) == 1
    assert data["file_level_direct_dependents"][0]["path"] == "src/core.py"
    
    # Depth 2 should have 2 affected files in each direction due to cycle handling in Phase 5.1
    # total_affected is the union of affected nodes.
    # main.py -> utils.py -> core.py
    # core.py -> main.py (visited)
    assert data["file_level_total_affected"] == 2

def test_symbol_impact_not_found_repo():
    response = client.get("/repositories/99/impact/symbol?path=src/main.py&symbol=main_func")
    assert response.status_code == 404

def test_symbol_impact_not_found_file():
    response = client.get("/repositories/1/impact/symbol?path=missing.py&symbol=main_func")
    assert response.status_code == 404

def test_symbol_impact_not_found_symbol():
    response = client.get("/repositories/1/impact/symbol?path=src/main.py&symbol=missing")
    assert response.status_code == 404

def test_symbol_impact_normalization():
    response = client.get("/repositories/1/impact/symbol?path=src\\main.py&symbol=main_func")
    assert response.status_code == 200
    assert response.json()["target_symbol"]["path"] == "src/main.py"

def test_symbol_impact_repo_isolation():
    response = client.get("/repositories/2/impact/symbol?path=src/main.py&symbol=main_func")
    assert response.status_code == 200
    assert response.json()["file_level_total_affected"] == 0

