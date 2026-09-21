import os
import shutil
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from models import Base, Repository, File, Symbol, Dependency, Chunk, Commit, CommitFileChange
from services.ingestion_job import process_repository
import database
import git

def setup_mock_git(repo_dir, files_content):
    os.makedirs(repo_dir, exist_ok=True)
    
    # Init git
    import git
    r = git.Repo.init(repo_dir)
    
    for path, content in files_content.items():
        full_path = os.path.join(repo_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)
        r.index.add([path])
    
    r.index.commit("Initial commit")
    return r

def run_tests():
    # 1. Setup isolated DB
    test_db_path = os.path.join(tempfile.gettempdir(), "test_deps.db")
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        
    engine = create_engine(f"sqlite:///{test_db_path}")
    Base.metadata.create_all(engine)
    
    # Overwrite SessionLocal for process_repository
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database.SessionLocal = TestingSessionLocal
    
    db = TestingSessionLocal()
    
    # 2. Setup mock repositories
    repo1_dir = os.path.join(tempfile.gettempdir(), "repo1")
    repo2_dir = os.path.join(tempfile.gettempdir(), "repo2")
    shutil.rmtree(repo1_dir, ignore_errors=True)
    shutil.rmtree(repo2_dir, ignore_errors=True)
    
    repo1_content = {
        "main.py": "import utils\nimport math\n",
        "utils.py": "def helper(): pass\n"
    }
    repo2_content = {
        "index.js": "import { func } from './lib';\n",
        "lib.js": "export const func = () => {};\n"
    }
    
    setup_mock_git(repo1_dir, repo1_content)
    setup_mock_git(repo2_dir, repo2_content)
    
    r1 = Repository(url=f"file://{repo1_dir}", status="pending")
    r2 = Repository(url=f"file://{repo2_dir}", status="pending")
    db.add(r1)
    db.add(r2)
    db.commit()
    
    print("Testing Ingestion 1")
    process_repository(r1.id)
    process_repository(r2.id)
    
    deps = db.query(Dependency).all()
    print(f"Deps after first ingestion: {len(deps)}")
    # Repo1: main.py imports utils and math -> 2 edges
    # Repo2: index.js imports ./lib -> 1 edge
    # Total: 3 edges
    assert len(deps) == 3, f"Expected 3 deps, got {len(deps)}"
    
    print("Testing Idempotency (unchanged re-ingestion)")
    process_repository(r1.id)
    process_repository(r2.id)
    
    deps2 = db.query(Dependency).all()
    print(f"Deps after second ingestion: {len(deps2)}")
    assert len(deps2) == 3, f"Expected 3 deps, got {len(deps2)}"
    
    print("Testing Change (add/remove imports)")
    # Modify Repo1
    with open(os.path.join(repo1_dir, "main.py"), "w") as f:
        # removed 'math', added 'os'
        f.write("import utils\nimport os\n")
        
    r = git.Repo(repo1_dir)
    r.index.add(["main.py"])
    r.index.commit("Second commit")
    
    process_repository(r1.id)
    
    deps3 = db.query(Dependency).all()
    print(f"Deps after changed ingestion: {len(deps3)}")
    assert len(deps3) == 3, f"Expected 3 deps, got {len(deps3)}"
    
    # Check edges specifically for Repo 1 main.py
    main_file = db.query(File).filter(File.repository_id == r1.id, File.path == "main.py").first()
    main_deps = db.query(Dependency).filter(Dependency.source_file_id == main_file.id).all()
    imported_modules = {d.imported_module for d in main_deps}
    print(f"Repo1 main.py imports now: {imported_modules}")
    assert imported_modules == {"utils", "os"}, f"Expected utils, os, got {imported_modules}"
    
    print("Testing Unresolved Imports handling")
    # In Repo 1, 'os' is unresolved (no os.py).
    os_dep = db.query(Dependency).filter(Dependency.source_file_id == main_file.id, Dependency.imported_module == "os").first()
    assert os_dep.target_file_id is None, "Expected os to be unresolved"
    
    print("Testing that repositories remain isolated")
    # Repo1 should not have Repo2's files as targets
    utils_dep = db.query(Dependency).filter(Dependency.source_file_id == main_file.id, Dependency.imported_module == "utils").first()
    target_file = db.query(File).filter(File.id == utils_dep.target_file_id).first()
    assert target_file.repository_id == r1.id, "Target file should be in same repo"
    
    print("Testing Extraction Failure handling")
    # Mock extract_imports to fail for main.py
    import services.ingestion_job
    original_extract_imports = services.ingestion_job.extract_imports
    
    def failing_extract_imports(file_path):
        if "main.py" in file_path:
            raise Exception("Simulated extraction failure")
        return original_extract_imports(file_path)
        
    services.ingestion_job.extract_imports = failing_extract_imports
    
    # Re-run ingestion. The dependencies for main.py should NOT be deleted.
    process_repository(r1.id)
    
    deps4 = db.query(Dependency).all()
    print(f"Deps after failing ingestion: {len(deps4)}")
    assert len(deps4) == 3, f"Expected 3 deps (preserved), got {len(deps4)}"
    
    main_deps_after = db.query(Dependency).filter(Dependency.source_file_id == main_file.id).all()
    imported_modules_after = {d.imported_module for d in main_deps_after}
    assert imported_modules_after == {"utils", "os"}, f"Expected utils, os to be preserved, got {imported_modules_after}"
    
    # Restore mock
    services.ingestion_job.extract_imports = original_extract_imports

    print("ALL TESTS PASSED")

if __name__ == '__main__':
    run_tests()
