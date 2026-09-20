import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import Repository, File, Dependency
from tests.test_search import setup_db
import uuid

client = TestClient(app)

@pytest.fixture
def impact_test_data(setup_db):
    db = SessionLocal()
    uid = uuid.uuid4().hex
    
    repo1 = Repository(url=f"https://github.com/test/repo1-{uid}", status="completed")
    repo2 = Repository(url=f"https://github.com/test/repo2-{uid}", status="completed")
    db.add_all([repo1, repo2])
    db.commit()
    db.refresh(repo1)
    db.refresh(repo2)
    
    f_a = File(repository_id=repo1.id, path="src/a.py")
    f_b = File(repository_id=repo1.id, path="src/b.py")
    f_c = File(repository_id=repo1.id, path="src/c.py")
    f_d = File(repository_id=repo1.id, path="src/d.py")
    
    # repo2 file
    f_e = File(repository_id=repo2.id, path="src/e.py")
    
    db.add_all([f_a, f_b, f_c, f_d, f_e])
    db.commit()
    
    for f in [f_a, f_b, f_c, f_d, f_e]:
        db.refresh(f)
        
    # A -> B -> C
    # C -> A (cycle)
    # D -> B
    
    dep1 = Dependency(source_file_id=f_a.id, target_file_id=f_b.id, imported_module="b")
    dep2 = Dependency(source_file_id=f_b.id, target_file_id=f_c.id, imported_module="c")
    dep3 = Dependency(source_file_id=f_c.id, target_file_id=f_a.id, imported_module="a")
    dep4 = Dependency(source_file_id=f_d.id, target_file_id=f_b.id, imported_module="b")
    
    # Null target dependency (unresolved)
    dep_unresolved = Dependency(source_file_id=f_a.id, target_file_id=None, imported_module="unknown")
    
    db.add_all([dep1, dep2, dep3, dep4, dep_unresolved])
    db.commit()
    
    repo1_id = repo1.id
    repo2_id = repo2.id
    db.close()
    
    return {
        "repo1_id": repo1_id,
        "repo2_id": repo2_id,
    }

def test_impact_direct_dependencies(impact_test_data):
    repo_id = impact_test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/impact?path=src/a.py&depth=1")
    assert response.status_code == 200
    data = response.json()
    
    assert data["depth"] == 1
    assert data["target"]["path"] == "src/a.py"
    
    # Direct dependencies of A is B
    assert len(data["direct_dependencies"]) == 1
    assert data["direct_dependencies"][0]["path"] == "src/b.py"
    
    # Direct dependents of A is C (due to cycle C->A)
    assert len(data["direct_dependents"]) == 1
    assert data["direct_dependents"][0]["path"] == "src/c.py"
    
    # Total affected: B, C
    assert data["total_affected"] == 2
    assert len(data["affected_files"]) == 2

def test_impact_depth_2_traversal(impact_test_data):
    repo_id = impact_test_data["repo1_id"]
    # Change A -> depth 2 should hit B, C and dependent C, B(from D? no D->B, B is not dependent on A)
    # Wait, A depends on B. B depends on C. (forward depth 2: B, C)
    # A is dependent on C. C is dependent on B. (backward depth 2: C, B)
    # A is NOT dependent on D. D depends on B, so if B changes, D is affected. 
    # Let's see if we change B, what happens.
    
    response = client.get(f"/repositories/{repo_id}/impact?path=src/b.py&depth=2")
    assert response.status_code == 200
    data = response.json()
    
    # B depends on C (depth 1). C depends on A (depth 2).
    # B is dependent on A (depth 1), D (depth 1). A is dependent on C (depth 2).
    
    assert data["total_affected"] == 3 # A, C, D
    affected_paths = [x["path"] for x in data["affected_files"]]
    assert "src/a.py" in affected_paths
    assert "src/c.py" in affected_paths
    assert "src/d.py" in affected_paths
    assert "src/b.py" not in affected_paths # Target itself omitted

def test_impact_normalization(impact_test_data):
    repo_id = impact_test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/impact?path=src\\a.py&depth=1")
    assert response.status_code == 200
    assert response.json()["target"]["path"] == "src/a.py"

def test_impact_unknown_repo_file(impact_test_data):
    repo_id = impact_test_data["repo1_id"]
    response = client.get(f"/repositories/99999/impact?path=src/a.py")
    assert response.status_code == 404
    
    response = client.get(f"/repositories/{repo_id}/impact?path=src/unknown.py")
    assert response.status_code == 404

def test_impact_repo_isolation(impact_test_data):
    repo_id = impact_test_data["repo2_id"]
    response = client.get(f"/repositories/{repo_id}/impact?path=src/a.py")
    assert response.status_code == 404 # a.py belongs to repo 1

def test_invalid_depth(impact_test_data):
    repo_id = impact_test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/impact?path=src/a.py&depth=11")
    assert response.status_code == 422 # FastAPI validation Error
