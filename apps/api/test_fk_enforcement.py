"""Foreign-key enforcement tests.

Every engine used here is created by tests/conftest.py inside pytest's temporary
directory. The persistent development database is never opened, not even for a
read-only PRAGMA check.
"""
import pytest
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from models import Base, Repository, File, Dependency, Commit, CommitFileChange, Chunk
# Importing database registers the shared connect listener that applies
# PRAGMA foreign_keys=ON to every sqlite connection in this process.
import database  # noqa: F401  (import for listener registration)


def test_app_engine_pragma(isolated_application_engine):
    """The application engine used by tests has PRAGMA foreign_keys=1.

    `isolated_application_engine` is conftest's session-scoped fixture that makes
    `database.engine` point at the temporary test database, so this assertion
    never touches the development database.
    """
    with database.engine.connect() as conn:
        res = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert res == 1, "Application engine should have PRAGMA foreign_keys=1"


def test_new_engine_pragma(tmp_path):
    """A newly created engine and its pooled connections enforce foreign keys."""
    db_path = str(tmp_path / "test_fk_pragma.db")
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)

    # Test fresh connection
    session = Session()
    res = session.execute(text("PRAGMA foreign_keys")).scalar()
    assert res == 1, "New engine should have PRAGMA foreign_keys=1"
    session.close()

    # Test pooled/reused connection
    session = Session()
    res = session.execute(text("PRAGMA foreign_keys")).scalar()
    assert res == 1, "Pooled connection should retain PRAGMA foreign_keys=1"
    session.close()
    engine.dispose()


@pytest.fixture
def test_session(tmp_path):
    """Provide a session connected to a fresh temporary SQLite database."""
    db_path = str(tmp_path / "test_fk_data.db")

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session
    session.close()
    engine.dispose()


def test_foreign_keys_enforcement(test_session):
    """5, 6, 7. Verify invalid FK cases explicitly fail and valid cases succeed, ensuring session usability."""
    session = test_session

    # --- File.repository_id ---
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        with session.begin_nested():
            f_invalid = File(repository_id=999, path="test.py", language="python")
            session.add(f_invalid)
            session.flush()

    # Valid File insertion proves session rollback (via begin_nested) left session usable
    r = Repository(url="https://test.com", status="completed")
    session.add(r)
    session.flush()

    f_valid = File(repository_id=r.id, path="test.py", language="python")
    session.add(f_valid)
    session.flush()
    assert f_valid.id is not None

    # --- Dependency.source_file_id ---
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        with session.begin_nested():
            d_invalid = Dependency(source_file_id=999, imported_module="os")
            session.add(d_invalid)
            session.flush()

    d_valid = Dependency(source_file_id=f_valid.id, imported_module="os")
    session.add(d_valid)
    session.flush()
    assert d_valid.id is not None

    # --- CommitFileChange.commit_id ---
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        with session.begin_nested():
            cfc_invalid = CommitFileChange(commit_id=999, file_id=f_valid.id, change_type="added", path="test.py")
            session.add(cfc_invalid)
            session.flush()

    c_valid = Commit(repository_id=r.id, sha="123", author_name="test", message="test", committed_at=datetime.now())
    session.add(c_valid)
    session.flush()

    cfc_valid = CommitFileChange(commit_id=c_valid.id, file_id=f_valid.id, change_type="added", path="test.py")
    session.add(cfc_valid)
    session.flush()
    assert cfc_valid.id is not None

    # --- Chunk.file_id ---
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        with session.begin_nested():
            chk_invalid = Chunk(repository_id=r.id, file_id=999, chunk_key="test", chunk_type="module", content="test", path="test.py", content_hash="hash")
            session.add(chk_invalid)
            session.flush()

    chk_valid = Chunk(repository_id=r.id, file_id=f_valid.id, chunk_key="test", chunk_type="module", content="test", path="test.py", content_hash="hash")
    session.add(chk_valid)
    session.flush()
    assert chk_valid.id is not None
