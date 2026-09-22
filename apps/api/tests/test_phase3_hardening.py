"""Phase 3 hardening tests.

Covers repository isolation, pagination bounds, empty/edge repositories and
Git extraction behaviour (empty history, initial commit, delete/rename).
Uses an isolated temporary SQLite database so the tracked database is untouched.
"""
import os
import subprocess
import sys
import tempfile
import shutil
from datetime import datetime, timedelta, UTC

import pytest
import git

# apps/api root (for main, database, models, schemas)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Monorepo root (for the top-level `services` package). Inserted last so it wins
# over apps/api/services, which would otherwise shadow it.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from fastapi.testclient import TestClient
from main import app
from database import Base
from models import (
    Repository,
    File as DBFile,
    Commit,
    CommitFileChange,
    RepositoryStatus,
)

REPO_A = 8201
REPO_B = 8202
REPO_EMPTY = 8203

# Import the Git service by file path to avoid shadowing by apps/api/services.
import importlib.util
_git_service_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "services", "ingestion", "git_service.py")
)
_spec = importlib.util.spec_from_file_location("phase3_git_service", _git_service_path)
_git_service = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_git_service)
extract_commits = _git_service.extract_commits
extract_commits_with_changes = _git_service.extract_commits_with_changes

# Assigned by setup_db from the conftest-provided test session factory.
_SessionLocal = None
client = TestClient(app)  # replaced with isolated-DB client in setup_db


@pytest.fixture(scope="module", autouse=True)
def setup_db(isolated_application_engine, TestingSessionLocal):
    # The temporary engine and schema come from conftest.py; Base.metadata is
    # already created there, so this fixture only seeds data.
    global _SessionLocal, client
    _SessionLocal = TestingSessionLocal
    client = TestClient(app)
    db = _SessionLocal()

    db.add(Repository(id=REPO_A, url="https://github.com/test/hard-a", status=RepositoryStatus.completed))
    db.add(Repository(id=REPO_B, url="https://github.com/test/hard-b", status=RepositoryStatus.completed))
    db.add(Repository(id=REPO_EMPTY, url="https://github.com/test/hard-empty", status=RepositoryStatus.completed))

    # Repo A: file + commit + change
    db.add(DBFile(id=8201, repository_id=REPO_A, path="src/a.py", language="python"))
    db.add(Commit(id=8201, repository_id=REPO_A, sha="sha-a1", message="A1",
                  committed_at=datetime(2026, 1, 1, 10, 0, 0)))
    db.add(Commit(id=8202, repository_id=REPO_A, sha="sha-a2", message="A2",
                  committed_at=datetime(2026, 1, 2, 10, 0, 0)))
    # Repo B: separate file + commit with its own distinct SHA
    db.add(DBFile(id=8202, repository_id=REPO_B, path="src/b.py", language="python"))
    db.add(Commit(id=8203, repository_id=REPO_B, sha="sha-b1", message="B1",
                  committed_at=datetime(2026, 1, 3, 10, 0, 0)))
    db.commit()

    db.add(CommitFileChange(commit_id=8201, file_id=8201, path="src/a.py", change_type="modified"))
    db.add(CommitFileChange(commit_id=8202, file_id=8201, path="src/a.py", change_type="added"))
    db.add(CommitFileChange(commit_id=8203, file_id=8202, path="src/b.py", change_type="added"))
    db.commit()
    db.close()

    yield

    db = _SessionLocal()
    db.query(CommitFileChange).filter(CommitFileChange.commit_id.in_([8201, 8202, 8203])).delete(synchronize_session=False)
    db.query(Commit).filter(Commit.repository_id.in_([REPO_A, REPO_B, REPO_EMPTY])).delete(synchronize_session=False)
    db.query(DBFile).filter(DBFile.repository_id.in_([REPO_A, REPO_B, REPO_EMPTY])).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id.in_([REPO_A, REPO_B, REPO_EMPTY])).delete(synchronize_session=False)
    db.commit()
    db.close()


# --------------------------------------------------------------------------
# Repository isolation
# --------------------------------------------------------------------------

def test_repo_a_cannot_see_repo_b_commits():
    response = client.get(f"/repositories/{REPO_A}/commits")
    assert response.status_code == 200
    shas = [item["sha"] for item in response.json()["items"]]
    assert "sha-b1" not in shas
    assert set(shas) == {"sha-a1", "sha-a2"}
    assert response.json()["total"] == 2


def test_repo_b_commit_sha_not_accessible_via_repo_a():
    # sha-b1 is a valid SHA, but it belongs to repo B
    response = client.get(f"/repositories/{REPO_A}/commits/sha-b1/changes")
    assert response.status_code == 404


def test_repo_b_file_id_not_accessible_via_repo_a():
    # file 8202 is valid, but owned by repo B
    assert client.get(f"/repositories/{REPO_A}/files/8202/churn").status_code == 404
    assert client.get(f"/repositories/{REPO_A}/files/8202/commits").status_code == 404


def test_hotspots_do_not_leak_across_repositories():
    data = client.get(f"/repositories/{REPO_A}/hotspots").json()
    paths = [row["path"] for row in data]
    assert "src/b.py" not in paths
    assert paths == ["src/a.py"]
    assert data[0]["total_changes"] == 2


def test_unknown_repository_is_404_for_all_phase3_endpoints(TestingSessionLocal):
    # The unknown id is derived from the isolated database, never hardcoded.
    db = TestingSessionLocal()
    known_ids = {row.id for row in db.query(Repository.id).all()}
    db.close()

    unknown = max(known_ids) + 1 if known_ids else 1
    assert unknown not in known_ids
    assert client.get(f"/repositories/{unknown}/commits").status_code == 404
    assert client.get(f"/repositories/{unknown}/commits/sha-a1/changes").status_code == 404
    assert client.get(f"/repositories/{unknown}/files/8201/commits").status_code == 404
    assert client.get(f"/repositories/{unknown}/files/8201/churn").status_code == 404
    assert client.get(f"/repositories/{unknown}/hotspots").status_code == 404


def test_unknown_file_is_404():
    # File ids are all below this sentinel in the isolated database.
    missing_file_id = 10 ** 9
    assert client.get(f"/repositories/{REPO_A}/files/{missing_file_id}/commits").status_code == 404
    assert client.get(f"/repositories/{REPO_A}/files/{missing_file_id}/churn").status_code == 404


def test_unknown_sha_is_404():
    assert client.get(f"/repositories/{REPO_A}/commits/does-not-exist/changes").status_code == 404


def test_empty_repository_returns_empty_results():
    assert client.get(f"/repositories/{REPO_EMPTY}/commits").json()["total"] == 0
    assert client.get(f"/repositories/{REPO_EMPTY}/commits").json()["items"] == []
    assert client.get(f"/repositories/{REPO_EMPTY}/hotspots").json() == []
    assert client.get(f"/repositories/{REPO_EMPTY}/files").json()["total"] == 0


def test_file_with_no_history_returns_zero_churn():
    db = _SessionLocal()
    db.add(DBFile(id=8299, repository_id=REPO_A, path="src/no_history.py", language="python"))
    db.commit()
    db.close()
    try:
        data = client.get(f"/repositories/{REPO_A}/files/8299/churn").json()
        assert data["total_changes"] == 0
        assert data["added_count"] == 0
        assert data["modified_count"] == 0
        assert data["deleted_count"] == 0
        assert data["renamed_count"] == 0
        assert client.get(f"/repositories/{REPO_A}/files/8299/commits").json()["total"] == 0
    finally:
        db = _SessionLocal()
        db.query(DBFile).filter(DBFile.id == 8299).delete()
        db.commit()
        db.close()


# --------------------------------------------------------------------------
# Pagination / validation bounds
# --------------------------------------------------------------------------

def test_malformed_ids_are_rejected_by_validation():
    assert client.get("/repositories/not-an-int/commits").status_code == 422
    assert client.get(f"/repositories/{REPO_A}/files/not-an-int/churn").status_code == 422


def test_page_below_one_is_422():
    assert client.get(f"/repositories/{REPO_A}/commits?page=0").status_code == 422
    assert client.get(f"/repositories/{REPO_A}/files/8201/commits?page=0").status_code == 422


def test_commit_limit_bounds():
    assert client.get(f"/repositories/{REPO_A}/commits?limit=0").status_code == 422
    assert client.get(f"/repositories/{REPO_A}/commits?limit=101").status_code == 422


def test_file_commits_limit_bounds():
    assert client.get(f"/repositories/{REPO_A}/files/8201/commits?limit=0").status_code == 422
    assert client.get(f"/repositories/{REPO_A}/files/8201/commits?limit=101").status_code == 422


def test_hotspot_limit_boundaries():
    assert client.get(f"/repositories/{REPO_A}/hotspots?limit=1").status_code == 200
    assert len(client.get(f"/repositories/{REPO_A}/hotspots?limit=1").json()) == 1
    assert client.get(f"/repositories/{REPO_A}/hotspots?limit=100").status_code == 200
    assert client.get(f"/repositories/{REPO_A}/hotspots?limit=101").status_code == 422
    assert client.get(f"/repositories/{REPO_A}/hotspots?limit=0").status_code == 422


def test_commits_newest_first_and_pagination_metadata():
    data = client.get(f"/repositories/{REPO_A}/commits?page=1&limit=1").json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["limit"] == 1
    assert len(data["items"]) == 1
    # newest first => A2 (Jan 2) before A1 (Jan 1)
    assert data["items"][0]["message"] == "A2"

    page2 = client.get(f"/repositories/{REPO_A}/commits?page=2&limit=1").json()
    assert page2["items"][0]["message"] == "A1"


def test_page_beyond_last_returns_empty_but_correct_total():
    data = client.get(f"/repositories/{REPO_A}/commits?page=99&limit=10").json()
    assert data["items"] == []
    assert data["total"] == 2


# --------------------------------------------------------------------------
# Git extraction edge cases (temporary local repositories)
# --------------------------------------------------------------------------

@pytest.fixture
def temp_git_repo():
    tmp = tempfile.mkdtemp()
    repo = git.Repo.init(tmp, initial_branch="main")
    writer = repo.config_writer()
    writer.set_value("user", "name", "Test").set_value("user", "email", "test@example.com").release()
    yield tmp, repo
    shutil.rmtree(tmp, ignore_errors=True)


def _write(path, name, text):
    with open(os.path.join(path, name), "w", encoding="utf-8") as handle:
        handle.write(text)


def test_extract_commits_from_repository_with_no_commits(temp_git_repo):
    path, _ = temp_git_repo
    # A repo with an unborn HEAD must not raise.
    assert extract_commits(path) == []
    assert extract_commits_with_changes(path) == []


def test_extract_commits_single_initial_commit_has_no_changes(temp_git_repo):
    path, repo = temp_git_repo
    _write(path, "only.py", "x = 1\n")
    repo.index.add(["only.py"])
    repo.index.commit("only commit")

    result = extract_commits_with_changes(path)
    assert len(result) == 1
    # Initial commit has no parent, so no diff is computed.
    assert result[0]["changes"] == []
    assert result[0]["message"] == "only commit"


def test_extract_commits_records_add_modify_delete_rename(temp_git_repo):
    path, repo = temp_git_repo
    _write(path, "a.py", "x = 1\n")
    repo.index.add(["a.py"])
    repo.index.commit("add a.py")

    _write(path, "a.py", "x = 2\n")
    repo.index.add(["a.py"])
    repo.index.commit("modify a.py")

    subprocess.run(["git", "-C", path, "mv", "a.py", "b.py"], check=True)
    repo.index.commit("rename a.py -> b.py")

    os.remove(os.path.join(path, "b.py"))
    repo.index.remove(["b.py"])
    repo.index.commit("delete b.py")

    by_message = {c["message"]: c["changes"] for c in extract_commits_with_changes(path)}

    assert by_message["add a.py"] == []
    assert by_message["modify a.py"] == [
        {"path": "a.py", "previous_path": None, "type": "modified"}
    ]
    assert by_message["rename a.py -> b.py"] == [
        {"path": "b.py", "previous_path": "a.py", "type": "renamed"}
    ]
    assert by_message["delete b.py"] == [
        {"path": "b.py", "previous_path": None, "type": "deleted"}
    ]


def test_extract_commits_preserves_multiline_message_and_multiple_files(temp_git_repo):
    path, repo = temp_git_repo
    _write(path, "a.py", "a = 1\n")
    repo.index.add(["a.py"])
    repo.index.commit("initial")

    _write(path, "a.py", "a = 2\n")
    _write(path, "b.py", "b = 1\n")
    repo.index.add(["a.py", "b.py"])
    commit = repo.index.commit("multi file commit\nwith a body line")

    result = extract_commits_with_changes(path)
    newest = next(c for c in result if c["sha"] == commit.hexsha)
    assert newest["message"].startswith("multi file commit")
    assert "with a body line" in newest["message"]
    # a.py existed in the previous commit, b.py is brand new in this one.
    changed = {change["path"]: change["type"] for change in newest["changes"]}
    assert changed == {"a.py": "modified", "b.py": "added"}


def test_extract_commits_handles_unicode_metadata(temp_git_repo):
    path, repo = temp_git_repo
    _write(path, "u.py", "u = 1\n")
    repo.index.add(["u.py"])
    repo.index.commit("unicode \u00e9\u4e2d\u6587 message")

    result = extract_commits(path)
    assert len(result) == 1
    assert "\u00e9\u4e2d\u6587" in result[0]["message"]
    assert result[0]["author_email"] == "test@example.com"


def test_extract_commits_only_yields_known_change_types(temp_git_repo):
    """Ingestion must only ever emit the four normalized change types."""
    path, repo = temp_git_repo
    _write(path, "a.py", "x = 1\n")
    repo.index.add(["a.py"])
    repo.index.commit("c1")
    _write(path, "a.py", "x = 2\n")
    repo.index.add(["a.py"])
    repo.index.commit("c2")
    subprocess.run(["git", "-C", path, "mv", "a.py", "b.py"], check=True)
    repo.index.commit("c3")
    os.remove(os.path.join(path, "b.py"))
    repo.index.remove(["b.py"])
    repo.index.commit("c4")

    allowed = {"added", "modified", "deleted", "renamed"}
    observed = {
        change["type"]
        for commit in extract_commits_with_changes(path)
        for change in commit["changes"]
    }
    assert observed <= allowed


def test_duplicate_commit_sha_in_same_repository_is_rejected():
    # The (repository_id, sha) uniqueness must hold at the schema level."
    from sqlalchemy.exc import IntegrityError
    db = _SessionLocal()
    db.add(Repository(id=8401, url="https://github.com/test/hard-dup", status=RepositoryStatus.completed))
    db.add(Commit(id=8401, repository_id=8401, sha="dup-sha", message="first",
                  committed_at=datetime(2026, 1, 1)))
    db.commit()
    try:
        db.add(Commit(id=8402, repository_id=8401, sha="dup-sha", message="second",
                      committed_at=datetime(2026, 1, 2)))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.query(Commit).filter(Commit.repository_id == 8401).delete(synchronize_session=False)
        db.query(Repository).filter(Repository.id == 8401).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_same_sha_allowed_in_different_repositories():
    # Uniqueness is per repository, so the same SHA may exist in two repos."
    db = _SessionLocal()
    db.add(Repository(id=8402, url="https://github.com/test/hard-dup-b", status=RepositoryStatus.completed))
    db.add(Commit(id=8403, repository_id=8402, sha="sha-a1", message="same sha, other repo",
                  committed_at=datetime(2026, 1, 1)))
    db.commit()
    try:
        assert db.query(Commit).filter(Commit.sha == "sha-a1").count() == 2
    finally:
        db.query(Commit).filter(Commit.repository_id == 8402).delete(synchronize_session=False)
        db.query(Repository).filter(Repository.id == 8402).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_hotspot_recent_window_boundary():
    """A change exactly at the 90-day boundary must count as recent."""
    db = _SessionLocal()
    repo = Repository(id=8301, url="https://github.com/test/hard-window", status=RepositoryStatus.completed)
    db.add(repo)
    db.add(DBFile(id=8301, repository_id=8301, path="src/window.py", language="python"))
    now = datetime.now(UTC)
    db.add(Commit(id=8301, repository_id=8301, sha="w-recent", message="recent",
                  committed_at=now - timedelta(days=89)))
    db.add(Commit(id=8302, repository_id=8301, sha="w-old", message="old",
                  committed_at=now - timedelta(days=91)))
    db.commit()
    db.add(CommitFileChange(commit_id=8301, file_id=8301, path="src/window.py", change_type="modified"))
    db.add(CommitFileChange(commit_id=8302, file_id=8301, path="src/window.py", change_type="modified"))
    db.commit()
    db.close()

    try:
        data = client.get("/repositories/8301/hotspots").json()
        assert len(data) == 1
        assert data[0]["total_changes"] == 2
        assert data[0]["recent_changes"] == 1
        expected = now - timedelta(days=89)
        actual = datetime.fromisoformat(data[0]["last_changed_at"]).replace(tzinfo=UTC)
        assert abs((actual - expected).total_seconds()) < 5
    finally:
        db = _SessionLocal()
        db.query(CommitFileChange).filter(CommitFileChange.commit_id.in_([8301, 8302])).delete(synchronize_session=False)
        db.query(Commit).filter(Commit.repository_id == 8301).delete(synchronize_session=False)
        db.query(DBFile).filter(DBFile.repository_id == 8301).delete(synchronize_session=False)
        db.query(Repository).filter(Repository.id == 8301).delete(synchronize_session=False)
        db.commit()
        db.close()
