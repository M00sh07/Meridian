import pytest
import uuid
from fastapi.testclient import TestClient
from main import app
from models import Repository, File, Dependency

# conftest.py installs the isolated DB override automatically (autouse=True).
client = TestClient(app)


@pytest.fixture
def impact_test_data(TestingSessionLocal):
    db = TestingSessionLocal()
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
    # Capture scalar ids before the session closes: the ORM instances become
    # detached on close, so touching `f_a.id` during teardown would raise.
    file_ids = [f_a.id, f_b.id, f_c.id, f_d.id, f_e.id]
    db.close()

    yield {"repo1_id": repo1_id, "repo2_id": repo2_id}

    db = TestingSessionLocal()
    db.query(Dependency).filter(Dependency.source_file_id.in_(file_ids)).delete(synchronize_session=False)
    db.query(File).filter(File.repository_id.in_([repo1_id, repo2_id])).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id.in_([repo1_id, repo2_id])).delete(synchronize_session=False)
    db.commit()
    db.close()


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
    response = client.get(f"/repositories/{repo_id}/impact?path=src/b.py&depth=2")
    assert response.status_code == 200
    data = response.json()

    assert data["total_affected"] == 3  # A, C, D
    affected_paths = [x["path"] for x in data["affected_files"]]
    assert "src/a.py" in affected_paths
    assert "src/c.py" in affected_paths
    assert "src/d.py" in affected_paths
    assert "src/b.py" not in affected_paths  # Target itself omitted


def test_impact_normalization(impact_test_data):
    repo_id = impact_test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/impact?path=src\\a.py&depth=1")
    assert response.status_code == 200
    assert response.json()["target"]["path"] == "src/a.py"


def test_impact_unknown_repo_file(impact_test_data):
    repo_id = impact_test_data["repo1_id"]
    response = client.get("/repositories/99999/impact?path=src/a.py")
    assert response.status_code == 404

    response = client.get(f"/repositories/{repo_id}/impact?path=src/unknown.py")
    assert response.status_code == 404


def test_impact_repo_isolation(impact_test_data):
    repo_id = impact_test_data["repo2_id"]
    response = client.get(f"/repositories/{repo_id}/impact?path=src/a.py")
    assert response.status_code == 404  # a.py belongs to repo 1


def test_invalid_depth(impact_test_data):
    repo_id = impact_test_data["repo1_id"]
    response = client.get(f"/repositories/{repo_id}/impact?path=src/a.py&depth=11")
    assert response.status_code == 422  # FastAPI validation Error
