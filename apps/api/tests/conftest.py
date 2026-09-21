"""Shared pytest fixtures providing a fully-isolated temporary database.

Every test module that requests `test_engine`, `TestingSessionLocal`, or
`db_session` from this file automatically operates on a per-session
SQLite database that is completely separate from apps/api/meredian.db.

Safety contract
---------------
* The database file lives inside pytest's `tmp_path_factory` temporary
  directory and is removed by the OS after the session ends.
* Every test database path passes through `_assert_not_production_db`.
  If a resolved path is apps/api/meredian.db, the run aborts immediately,
  so the persistent database can never be opened or dropped by tests.
* The application's `database.engine` and `database.SessionLocal` are
  rebound to the test engine for the whole session, because application
  code (for example `services.ingestion_job.process_repository`) reads
  `SessionLocal` from the `database` module.
* `drop_all()` only ever runs on the temporary engine, in that engine's
  own session-scoped teardown.
* `app.dependency_overrides[get_db]` is installed globally for the entire
  test session so that every FastAPI TestClient uses the same isolated DB.
"""
import os
import sys

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Ensure apps/api is on sys.path (tests are run from apps/api root).
# ---------------------------------------------------------------------------
_api_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

# Monorepo root for the top-level `services` package.
_mono_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _mono_root not in sys.path:
    sys.path.append(_mono_root)

import database  # noqa: E402  (after sys.path setup)
from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402
# ---------------------------------------------------------------------------
# Hard safety guard
# ---------------------------------------------------------------------------

#: Absolute path of the persistent development database. No test is ever
#: allowed to open, create, or drop this file.
PRODUCTION_DB_PATH = os.path.normcase(
    os.path.abspath(os.path.join(_api_root, "meredian.db"))
)


def _assert_not_production_db(db_path: str) -> None:
    """Abort immediately if a test database path resolves to meredian.db.

    Fails when the path *is* the production file, and also when it merely
    contains that absolute path, because either way the run would be operating
    on real development data.
    """
    resolved = os.path.normcase(os.path.abspath(db_path))
    assert resolved != PRODUCTION_DB_PATH, (
        "SAFETY ABORT: a test resolved to the persistent development database!\n"
        f"  resolved:  {resolved}\n"
        f"  forbidden: {PRODUCTION_DB_PATH}"
    )
    assert PRODUCTION_DB_PATH not in resolved, (
        "SAFETY ABORT: a test path points into the persistent development "
        f"database location.\n  resolved:  {resolved}\n"
        f"  forbidden: {PRODUCTION_DB_PATH}"
    )


def _guard_url(url) -> None:
    """Abort if `url` would connect to the persistent development database."""
    try:
        parsed = make_url(str(url))
    except Exception:
        return
    if parsed.get_backend_name() != "sqlite":
        return
    db_file = parsed.database or ""
    if db_file in ("", ":memory:"):
        return
    _assert_not_production_db(db_file)


def _install_engine_guard():
    """Refuse to create any engine that points at the persistent database.

    Rebinding `database.engine` is not by itself a guarantee: application code
    may call `sqlalchemy.create_engine` directly. This wraps `create_engine` for
    the whole process, so opening the persistent database fails loudly whatever
    the calling convention.

    Returns the original `create_engine` so it can be restored.
    """
    import sqlalchemy

    original_create_engine = sqlalchemy.create_engine

    def guarded_create_engine(url, *args, **kwargs):
        _guard_url(url)
        return original_create_engine(url, *args, **kwargs)

    sqlalchemy.create_engine = guarded_create_engine
    return original_create_engine


def _rebind_modules_holding_session_local(session_local) -> dict:
    """Rebind `SessionLocal` in every module that imported it by name.

    `services/ingestion_job.py` does `from database import SessionLocal`, so
    changing `database.SessionLocal` alone leaves that module pointed at the
    original engine. This walks already-imported modules and swaps the
    reference, returning the previous values so they can be restored.
    """
    previous = {}
    for module_name, module in list(sys.modules.items()):
        if module is None:
            continue
        current = getattr(module, "SessionLocal", None)
        # Only swap a factory that is actually bound to an engine, i.e. a real
        # application session factory rather than an unrelated attribute.
        if current is None or getattr(current, "kw", None) is None:
            continue
        if "bind" not in current.kw:
            continue
        previous[module_name] = current
        module.SessionLocal = session_local
    return previous


def _assert_isolated_engine(engine) -> None:
    """Abort if a SQLAlchemy engine points at the persistent database."""
    url = make_url(str(engine.url))
    if url.get_backend_name() != "sqlite":
        return
    db_file = url.database or ""
    if db_file in ("", ":memory:"):
        return
    _assert_not_production_db(db_file)


def pytest_configure(config):
    """Guard the pytest temp directory before any test is collected.

    Every test database is created under pytest's basetemp, so if that
    directory ever pointed at apps/api the run must stop immediately.
    """
    _assert_not_production_db(str(config.option.basetemp or ""))

# ---------------------------------------------------------------------------
# Session-scoped temporary engine / sessionmaker
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_engine(tmp_path_factory):
    """Return a SQLAlchemy engine backed by a temporary SQLite file.

    The file is created inside pytest's own temp directory and is never
    inside the repository tree, so it cannot be the production database.
    """
    tmp = tmp_path_factory.mktemp("testdb")
    db_path = str(tmp / "test.db")

    # Hard safety: must not resolve to the production database.
    _assert_not_production_db(db_path)

    url = f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    _assert_isolated_engine(engine)

    Base.metadata.create_all(bind=engine)
    yield engine
    # drop_all() is only ever allowed here: `engine` is the temporary test
    # engine created above, never the application engine.
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session")
def TestingSessionLocal(test_engine):  # noqa: N802
    """Return a sessionmaker bound to the isolated test engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(autouse=True)
def _ensure_temp_schema(test_engine):
    """Ensure the temporary schema exists; never clear data between tests.

    Module-scoped autouse fixtures seed rows during their own setup, so
    wiping between tests would race them. Each module tears down the rows
    it created, and the whole database file is deleted with pytest's
    temporary directory at the end of the session.
    """
    _assert_isolated_engine(test_engine)
    Base.metadata.create_all(bind=test_engine)

# ---------------------------------------------------------------------------
# Keep application code off the persistent database
# ---------------------------------------------------------------------------

@event.listens_for(Engine, "connect")
def _set_test_fk_pragma(dbapi_connection, connection_record):
    """Enable FK enforcement on every connection (mirrors production database.py).

    conftest is imported once per pytest process, so this listener is not
    duplicated across modules.
    """
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

@pytest.fixture(scope="session", autouse=True)
def isolated_application_engine(test_engine, TestingSessionLocal):  # noqa: N803
    """Rebind the application's engine/session factory to the test database.

    `services.ingestion_job.process_repository` opens its own session from
    `SessionLocal`. Without this rebinding, tests that run the real ingestion
    pipeline would write into apps/api/meredian.db.

    Three things are done, because one alone is not enough:
      1. `database.engine` and `database.SessionLocal` are rebound.
      2. Every already-imported module that captured `SessionLocal` via
         `from database import SessionLocal` is rebound too.
      3. `sqlalchemy.create_engine` is wrapped so any sqlite engine pointing at
         the persistent database is refused for the whole process.

    The originals are restored afterwards so other contexts are unaffected.
    """
    _assert_isolated_engine(test_engine)

    original_engine = database.engine
    original_session_local = database.SessionLocal
    original_create_engine = _install_engine_guard()

    database.engine = test_engine
    database.SessionLocal = TestingSessionLocal
    previous_module_bindings = _rebind_modules_holding_session_local(TestingSessionLocal)
    try:
        yield
    finally:
        for module_name, previous in previous_module_bindings.items():
            module = sys.modules.get(module_name)
            if module is not None:
                module.SessionLocal = previous
        database.engine = original_engine
        database.SessionLocal = original_session_local
        import sqlalchemy

        sqlalchemy.create_engine = original_create_engine
@pytest.fixture(autouse=True)
def _assert_isolated_engine_per_test(isolated_application_engine, test_engine):
    """Re-verify, for every single test, that no engine points at real data.

    This catches a module-level rebinding such as
    `database.engine = create_engine("sqlite:///.../meredian.db")` before the
    test body runs, rather than after the damage is done.
    """
    _assert_isolated_engine(database.engine)
    _assert_isolated_engine(test_engine)

    # Direct `from database import SessionLocal` consumers must also be bound to
    # the temporary engine, not just the `database` attribute.
    for name, module in list(sys.modules.items()):
        if module is None or name.startswith(("tests.", "_pytest", "pytest")):
            continue
        session_local = getattr(module, "SessionLocal", None)
        if session_local is None or getattr(session_local, "kw", None) is None:
            continue
        bind = session_local.kw.get("bind")
        if bind is not None:
            _assert_isolated_engine(bind)

    with test_engine.connect() as connection:
        file_name = connection.execute(text("PRAGMA database_list")).fetchone()[2]
    _assert_not_production_db(file_name or "")

# ---------------------------------------------------------------------------
# Override FastAPI's get_db dependency for every test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def override_get_db(TestingSessionLocal):  # noqa: N803
    """Install the test session factory as the FastAPI DB dependency.

    If another module has already installed its own override at import time,
    we save and restore it rather than clobbering it.

    `autouse=True` + `scope="session"` means this runs once for the whole session.
    Tests that accept `TestingSessionLocal` directly still get the shared isolated DB.
    The dependency override ensures FastAPI endpoints also use it.
    """
    _previous = app.dependency_overrides.get(get_db)

    def _get_test_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    # Restore whatever was there before (or remove if nothing was).
    if _previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = _previous
@pytest.fixture(autouse=True)
def verify_direct_sessionlocal_binding(test_engine):
    """Prove the module-level `SessionLocal` in application code is isolated.

    The FastAPI `get_db` override only covers endpoints. Code that closes over
    `SessionLocal` at import time -- most importantly
    `services.ingestion_job.process_repository`, which does
    `from database import SessionLocal` and then `SessionLocal()` per call --
    would otherwise write into apps/api/meredian.db during tests.

    This assertion runs before every test and fails the run rather than letting
    a single row reach the persistent database.
    """
    import services.ingestion_job as ingestion_job
    _assert_isolated_engine(database.engine)
    _assert_isolated_engine(test_engine)

    # The imported name must be the same object as the rebound session factory,
    # otherwise application code would open sessions on the persistent database.
    assert ingestion_job.SessionLocal is database.SessionLocal, (
        "services.ingestion_job.SessionLocal is not the isolated test factory; "
        "it would write to the persistent development database."
    )

    session = ingestion_job.SessionLocal()
    try:
        assert session.get_bind() is test_engine, (
            "services.ingestion_job sessions are not bound to the temporary "
            "test engine."
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Convenience per-test db session
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session(TestingSessionLocal):  # noqa: N803
    """Yield a fresh DB session for a single test; closed on teardown."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Shared search fixtures
# (used by test_search / test_hybrid_search / test_context_assembly)
# ---------------------------------------------------------------------------

@pytest.fixture
def search_test_data(TestingSessionLocal):  # noqa: N803
    """Two isolated repositories containing chunked, embedded content.

    Repository ids are allocated by the database rather than hardcoded, and
    every row created here is deleted on teardown so the fixture can be reused
    by several modules safely.
    """
    import uuid

    from models import Chunk, File, Repository

    db = TestingSessionLocal()

    uid = uuid.uuid4().hex
    repo1 = Repository(url=f"https://github.com/test/repo1-{uid}", status="completed")
    repo2 = Repository(url=f"https://github.com/test/repo2-{uid}", status="completed")
    db.add(repo1)
    db.add(repo2)
    db.commit()
    db.refresh(repo1)
    db.refresh(repo2)

    repo1_id = repo1.id
    repo2_id = repo2.id

    file1 = File(repository_id=repo1_id, path="src/auth.py", language="python")
    file2 = File(repository_id=repo1_id, path="src/db.py", language="python")
    file3 = File(repository_id=repo2_id, path="src/auth.py", language="python")
    db.add_all([file1, file2, file3])
    db.commit()
    db.refresh(file1)
    db.refresh(file2)
    db.refresh(file3)

    # repo 1 chunks
    chunk1 = Chunk(
        repository_id=repo1_id,
        file_id=file1.id,
        chunk_key=f"c1-{uid}",
        chunk_type="function",
        path="src/auth.py",
        symbol_name="login",
        language="python",
        content="def login(): pass # authentication",
        content_hash="h1",
        embedding=[0.9, 0.1, 0.0],
        embedded_content_hash="h1",
    )
    chunk2 = Chunk(
        repository_id=repo1_id,
        file_id=file2.id,
        chunk_key=f"c2-{uid}",
        chunk_type="class",
        path="src/db.py",
        symbol_name="Database",
        language="python",
        content="class Database: pass # database connection",
        content_hash="h2",
        embedding=[0.1, 0.9, 0.0],
        embedded_content_hash="h2",
    )
    chunk3 = Chunk(
        repository_id=repo1_id,
        file_id=file1.id,
        chunk_key=f"c3-{uid}",
        chunk_type="function",
        path="src/auth.py",
        symbol_name="logout",
        language="python",
        content="def logout(): pass # other",
        content_hash="h3",
        embedding=[0.0, 0.1, 0.9],
        embedded_content_hash="h3",
    )

    # repo 2 chunk: must never appear in repo 1 results
    chunk4 = Chunk(
        repository_id=repo2_id,
        file_id=file3.id,
        chunk_key=f"c4-{uid}",
        chunk_type="function",
        path="src/auth.py",
        symbol_name="login",
        language="python",
        content="def login(): pass # authentication repo2",
        content_hash="h4",
        embedding=[0.95, 0.05, 0.0],
        embedded_content_hash="h4",
    )

    # unembedded chunk
    chunk5 = Chunk(
        repository_id=repo1_id,
        file_id=file1.id,
        chunk_key=f"c5-{uid}",
        chunk_type="module",
        path="src/utils.py",
        language="python",
        content="some utils",
        content_hash="h5",
        embedding=None,
    )

    db.add_all([chunk1, chunk2, chunk3, chunk4, chunk5])
    db.commit()

    # Make the chunk ids deterministic for assertions that inspect ordering.
    repo1_chunks = {
        chunk.chunk_key.split("-")[0]: chunk.id
        for chunk in db.query(Chunk).filter(Chunk.repository_id == repo1_id).all()
    }

    yield {
        "repo1_id": repo1_id,
        "repo2_id": repo2_id,
        "chunk_ids": repo1_chunks,
    }

    # Teardown: remove only the rows this fixture inserted.
    db.query(Chunk).filter(Chunk.repository_id.in_([repo1_id, repo2_id])).delete(synchronize_session=False)
    db.query(File).filter(File.repository_id.in_([repo1_id, repo2_id])).delete(synchronize_session=False)
    db.query(Repository).filter(Repository.id.in_([repo1_id, repo2_id])).delete(synchronize_session=False)
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Proof helpers
# ---------------------------------------------------------------------------

def test_database_is_not_the_persistent_file(test_engine, tmp_path):
    """Prove the test database is ephemeral and never the development database.

    This guard test lives in conftest so it runs with every targeted selection
    and documents the isolation contract in executable form.
    """
    url = make_url(str(test_engine.url))
    db_file = os.path.abspath(url.database)

    # 1. It is not the persistent development database.
    _assert_not_production_db(db_file)

    # 2. It lives under pytest's own temporary directory.
    temp_root = os.path.normcase(os.path.abspath(str(tmp_path.parent)))
    assert os.path.normcase(db_file).startswith(temp_root), (
        f"test database {db_file} is not under the pytest temp directory {temp_root}"
    )

    # 3. It is not inside the repository tree at all.
    repo_root = os.path.normcase(os.path.abspath(os.path.join(_api_root, "..")))
    assert not os.path.normcase(db_file).startswith(repo_root), (
        f"test database {db_file} must not be created inside the repository"
    )

    # 4. No harness database artifacts are left in apps/api.
    stray = [
        name
        for name in os.listdir(_api_root)
        if name.endswith(".db") and name != "meredian.db" and name.startswith("test")
    ]
    assert stray == [], f"persistent test databases found in apps/api: {stray}"
