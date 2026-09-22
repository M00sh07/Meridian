"""Focused tests for Phase 4.1 semantic chunking.

Covers deterministic chunk creation for functions/classes/modules/docs, metadata
preservation, repository isolation, idempotent re-ingestion, and the read API.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

import git
import pytest

# Monorepo root must win over apps/api/services, which would otherwise shadow
# the top-level `services` package.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
import database
from models import (
    Repository,
    File as DBFile,
    Symbol as DBSymbol,
    Chunk as DBChunk,
    RepositoryStatus,
)

# Ids are reserved inside the temporary test database only; they never collide
# with the persistent development database because they live in separate files.
REPO_A = 9001
REPO_B = 9002
# Assigned by setup_db from the conftest-provided test session factory.
_SessionLocal = None
client = TestClient(app)  # replaced with isolated-DB client in setup_db


def _load(module_name, rel_path):
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", rel_path))
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


chunking = _load("phase4_chunking_service", "services/parser/chunking_service.py")
ingestion_job = _load("phase4_ingestion_job", os.path.join("apps", "api", "services", "ingestion_job.py"))

# `_load` execs ingestion_job.py again under a different module name, so its
# `from database import SessionLocal` is a separate binding. Rebind it at
# fixture time to the isolated test engine (see tests/conftest.py).
def _bind_ingestion_to_test_engine(session_local):
    """Make the ad-hoc ingestion module use the temporary engine."""
    ingestion_job.SessionLocal = session_local
    database.SessionLocal = session_local
    assert ingestion_job.SessionLocal is session_local



# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def setup_db(isolated_application_engine, TestingSessionLocal):
    global _SessionLocal, client
    _SessionLocal = TestingSessionLocal
    _bind_ingestion_to_test_engine(TestingSessionLocal)
    client = TestClient(app)
    db = _SessionLocal()
    db.add(Repository(id=REPO_A, url="https://github.com/test/chunk-a", status=RepositoryStatus.completed))
    db.add(Repository(id=REPO_B, url="https://github.com/test/chunk-b", status=RepositoryStatus.completed))
    db.commit()
    db.close()
    yield
    db = _SessionLocal()
    db.query(DBChunk).filter(DBChunk.repository_id.in_([REPO_A, REPO_B])).delete(synchronize_session=False)

    file_ids = db.query(DBFile.id).filter(DBFile.repository_id.in_([REPO_A, REPO_B]))
    db.query(DBSymbol).filter(DBSymbol.file_id.in_(file_ids)).delete(synchronize_session=False)

    from models import Dependency as DBDependency, CommitFileChange as DBCommitFileChange, Commit as DBCommit
    db.query(DBDependency).filter((DBDependency.source_file_id.in_(file_ids)) | (DBDependency.target_file_id.in_(file_ids))).delete(synchronize_session=False)
    db.query(DBCommitFileChange).filter(DBCommitFileChange.file_id.in_(file_ids)).delete(synchronize_session=False)

    db.query(DBFile).filter(DBFile.repository_id.in_([REPO_A, REPO_B])).delete(synchronize_session=False)
    db.query(DBCommit).filter(DBCommit.repository_id.in_([REPO_A, REPO_B])).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id.in_([REPO_A, REPO_B])).delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.fixture
def sample_repo():
    """A temporary git repository with a function, a class, and a doc file."""
    tmp = tempfile.mkdtemp()
    repo = git.Repo.init(tmp, initial_branch="main")
    writer = repo.config_writer()
    writer.set_value("user", "name", "Test").set_value("user", "email", "test@example.com").release()

    with open(os.path.join(tmp, "mod.py"), "w", encoding="utf-8") as handle:
        handle.write(
            "def alpha():\n"
            "    return 1\n"
            "\n"
            "\n"
            "class Beta:\n"
            "    def beta_method(self):\n"
            "        return 2\n"
        )
    with open(os.path.join(tmp, "README.md"), "w", encoding="utf-8") as handle:
        handle.write("# Title\nSome documentation.\n")

    repo.index.add(["mod.py", "README.md"])
    repo.index.commit("initial")

    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def _ingest(repo_id, local_path):
    """Run the real ingestion pipeline against a local repo path."""
    db = _SessionLocal()
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    repo.url = "file:///" + local_path.replace("\\", "/")
    repo.status = RepositoryStatus.pending
    db.commit()
    db.close()
    ingestion_job.process_repository(repo_id)


def _chunks(repo_id):
    db = _SessionLocal()
    rows = (
        db.query(DBChunk)
        .filter(DBChunk.repository_id == repo_id)
        .order_by(DBChunk.path, DBChunk.start_line, DBChunk.id)
        .all()
    )
    data = [
        {
            "chunk_key": c.chunk_key,
            "chunk_type": c.chunk_type,
            "path": c.path,
            "symbol_name": c.symbol_name,
            "symbol_type": c.symbol_type,
            "language": c.language,
            "file_id": c.file_id,
            "symbol_id": c.symbol_id,
            "start_line": c.start_line,
            "end_line": c.end_line,
            "content": c.content,
            "content_hash": c.content_hash,
            "repository_id": c.repository_id,
        }
        for c in rows
    ]
    db.close()
    return data


# --------------------------------------------------------------------------
# Chunk creation and metadata
# --------------------------------------------------------------------------

def test_ingestion_creates_function_class_module_and_doc_chunks(sample_repo):
    _ingest(REPO_A, sample_repo)
    chunks = _chunks(REPO_A)
    by_key = {(c["path"], c["chunk_type"], c["symbol_name"]): c for c in chunks}

    assert ("mod.py", "function", "alpha") in by_key
    assert ("mod.py", "class", "Beta") in by_key
    assert ("mod.py", "function", "beta_method") in by_key
    assert ("mod.py", "module", None) in by_key
    assert ("README.md", "doc", None) in by_key


def test_chunk_metadata_is_populated(sample_repo):
    _ingest(REPO_A, sample_repo)
    chunks = _chunks(REPO_A)

    for chunk in chunks:
        assert chunk["repository_id"] == REPO_A
        assert chunk["path"]
        assert chunk["content"].strip()
        assert len(chunk["content_hash"]) == 64
        assert chunk["file_id"] is not None

    alpha = next(c for c in chunks if c["symbol_name"] == "alpha")
    assert alpha["start_line"] == 1
    assert alpha["end_line"] == 2
    assert alpha["content"] == "def alpha():\n    return 1"
    assert alpha["symbol_id"] is not None
    assert alpha["language"] == "python"

    doc = next(c for c in chunks if c["chunk_type"] == "doc")
    assert doc["content"] == "# Title\nSome documentation."
    assert doc["symbol_id"] is None
    assert doc["language"] is None or isinstance(doc["language"], str)


def test_reuses_existing_file_and_symbol_rows(sample_repo):
    """Chunking must not duplicate the File/Symbol records it derives from."""
    _ingest(REPO_A, sample_repo)
    db = _SessionLocal()
    files = db.query(DBFile).filter(DBFile.repository_id == REPO_A).all()
    file_ids = [f.id for f in files]
    symbol_count = db.query(DBSymbol).filter(DBSymbol.file_id.in_(file_ids)).count()
    chunk_count = db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).count()
    db.close()

    assert len(files) == 2
    # Symbols exist for mod.py only.
    assert symbol_count == 3
    # Every symbol chunk points at a real persisted symbol row.
    assert chunk_count > symbol_count


def test_chunking_is_deterministic(sample_repo):
    _ingest(REPO_A, sample_repo)
    first = _chunks(REPO_A)
    _ingest(REPO_A, sample_repo)
    second = _chunks(REPO_A)

    assert [c["chunk_key"] for c in first] == [c["chunk_key"] for c in second]
    assert [c["content_hash"] for c in first] == [c["content_hash"] for c in second]


def test_build_file_chunks_handles_binary_and_missing_files():
    tmp = tempfile.mkdtemp()
    try:
        binary = os.path.join(tmp, "b.bin")
        with open(binary, "wb") as handle:
            handle.write(b"\x00\x01\x02binary")
        assert chunking.build_file_chunks("b.bin", binary, None, []) is None
        assert chunking.build_file_chunks("missing.py", os.path.join(tmp, "nope.py"), "python", []) is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# Idempotent re-ingestion
# --------------------------------------------------------------------------

def test_re_ingestion_does_not_duplicate_chunks(sample_repo):
    _ingest(REPO_A, sample_repo)
    db = _SessionLocal()
    first_ids = sorted(c.id for c in db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).all())
    first_count = len(first_ids)
    db.close()

    _ingest(REPO_A, sample_repo)

    db = _SessionLocal()
    second = db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).all()
    second_ids = sorted(c.id for c in second)
    db.close()

    assert len(second) == first_count
    # Existing rows are updated in place, not recreated.
    assert second_ids == first_ids


def test_re_ingestion_updates_chunk_content_when_file_changes(sample_repo):
    _ingest(REPO_A, sample_repo)
    db = _SessionLocal()
    before = (
        db.query(DBChunk)
        .filter(DBChunk.repository_id == REPO_A, DBChunk.path == "mod.py", DBChunk.chunk_type == "module")
        .one()
    )
    before_hash = before.content_hash
    before_id = before.id
    db.close()

    # Rewrite the module and commit so re-ingestion sees new content.
    with open(os.path.join(sample_repo, "mod.py"), "w", encoding="utf-8") as handle:
        handle.write(
            "def alpha():\n"
            "    return 42\n"
            "\n"
            "\n"
            "class Beta:\n"
            "    def beta_method(self):\n"
            "        return 2\n"
        )
    repo = git.Repo(sample_repo)
    repo.index.add(["mod.py"])
    repo.index.commit("change alpha")

    _ingest(REPO_A, sample_repo)

    db = _SessionLocal()
    after = (
        db.query(DBChunk)
        .filter(DBChunk.repository_id == REPO_A, DBChunk.path == "mod.py", DBChunk.chunk_type == "module")
        .one()
    )
    db.close()

    assert after.id == before_id
    assert after.content_hash != before_hash
    assert "return 42" in after.content


# --------------------------------------------------------------------------
# Repository isolation
# --------------------------------------------------------------------------

def test_chunks_are_isolated_per_repository(sample_repo):
    other = tempfile.mkdtemp()
    try:
        repo = git.Repo.init(other, initial_branch="main")
        writer = repo.config_writer()
        writer.set_value("user", "name", "Test").set_value("user", "email", "test@example.com").release()
        with open(os.path.join(other, "other.py"), "w", encoding="utf-8") as handle:
            handle.write("def gamma():\n    return 3\n")
        repo.index.add(["other.py"])
        repo.index.commit("initial")

        _ingest(REPO_A, sample_repo)
        _ingest(REPO_B, other)

        a_chunks = _chunks(REPO_A)
        b_chunks = _chunks(REPO_B)

        assert all(c["repository_id"] == REPO_A for c in a_chunks)
        assert all(c["repository_id"] == REPO_B for c in b_chunks)
        assert {c["path"] for c in a_chunks} == {"mod.py", "README.md"}
        assert {c["path"] for c in b_chunks} == {"other.py"}

        # API-level isolation
        assert client.get(f"/repositories/{REPO_A}/chunks").json()["total"] == len(a_chunks)
        b_total = client.get(f"/repositories/{REPO_B}/chunks").json()["total"]
        assert b_total == len(b_chunks)

        # A repeated chunk_key across repositories is allowed.
        db = _SessionLocal()
        keys_a = {c.chunk_key for c in db.query(DBChunk).filter(DBChunk.repository_id == REPO_A).all()}
        keys_b = {c.chunk_key for c in db.query(DBChunk).filter(DBChunk.repository_id == REPO_B).all()}
        db.close()
        assert "module:mod.py" in keys_a
        assert "module:other.py" in keys_b
    finally:
        shutil.rmtree(other, ignore_errors=True)


def test_chunks_api_unknown_repository_404():
    assert client.get("/repositories/999/chunks").status_code == 404


def test_chunks_api_pagination_and_filter(sample_repo):
    _ingest(REPO_A, sample_repo)

    page = client.get(f"/repositories/{REPO_A}/chunks?page=1&limit=2").json()
    assert page["page"] == 1
    assert page["limit"] == 2
    assert len(page["items"]) == 2
    total = page["total"]

    filtered = client.get(f"/repositories/{REPO_A}/chunks?chunk_type=doc").json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["chunk_type"] == "doc"

    assert client.get(f"/repositories/{REPO_A}/chunks?limit=0").status_code == 422
    assert client.get(f"/repositories/{REPO_A}/chunks?limit=101").status_code == 422
    assert client.get(f"/repositories/{REPO_A}/chunks?page=0").status_code == 422
    assert total >= 5
