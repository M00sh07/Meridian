import os
import tempfile
import pytest
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from models import Base, Repository, File, Dependency, Commit, CommitFileChange, Chunk

# Import database module to ensure event listener is registered and to test the app engine
import database


def test_app_engine_pragma():
    """1. Verify the actual application's database.engine has PRAGMA foreign_keys=1."""
    with database.engine.connect() as conn:
        res = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert res == 1, "Application engine should have PRAGMA foreign_keys=1"


def test_new_engine_pragma():
    """2 & 3. Verify newly created engine and pooled connections have PRAGMA foreign_keys=1."""
    db_path = os.path.join(tempfile.gettempdir(), "test_fk_pragma.db")
    if os.path.exists(db_path):
        os.remove(db_path)

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


@pytest.fixture
def test_session():
    """Provides a session connected to a fresh temporary SQLite database."""
    db_path = os.path.join(tempfile.gettempdir(), "test_fk_data.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


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
