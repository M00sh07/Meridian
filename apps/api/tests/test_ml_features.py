from fastapi.testclient import TestClient
from datetime import datetime, timedelta, UTC
import pytest
import math
from database import Base, get_db, SessionLocal
from models import Repository, Commit, CommitFileChange, RepositoryStatus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.ml.features import extract_features, BASELINE_FEATURES, ALL_FEATURES

engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    repo = Repository(url="https://github.com/test/features", status=RepositoryStatus.completed, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    repo_b = Repository(url="https://github.com/test/other", status=RepositoryStatus.completed, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    db.add(repo)
    db.add(repo_b)
    db.commit()

    base_time = datetime(2025, 1, 1, tzinfo=UTC)

    # Commit 1: touches file_a (dir1), file_b (dir1)
    c1 = Commit(repository_id=repo.id, sha="c1", message="init", author_name="test", author_email="test", committed_at=base_time)
    db.add(c1)
    db.flush()
    db.add(CommitFileChange(commit_id=c1.id, path="dir1/file_a.py", change_type="added"))
    db.add(CommitFileChange(commit_id=c1.id, path="dir1/file_b.py", change_type="added"))
    db.commit()

    # Commit 2: touches file_a again
    c2 = Commit(repository_id=repo.id, sha="c2", message="upd", author_name="test", author_email="test", committed_at=base_time + timedelta(days=1))
    db.add(c2)
    db.flush()
    db.add(CommitFileChange(commit_id=c2.id, path="dir1/file_a.py", change_type="modified"))
    db.commit()

    # Add 12 more commits to file_a to trigger HIGH_CHURN_THRESHOLD (>10)
    for i in range(12):
        c = Commit(repository_id=repo.id, sha=f"c2_{i}", message="churn", author_name="test", author_email="test", committed_at=base_time + timedelta(days=2+i))
        db.add(c)
        db.flush()
        db.add(CommitFileChange(commit_id=c.id, path="dir1/file_a.py", change_type="modified"))
    db.commit()

    # Target Commit: touches file_a, file_c (dir2). We also duplicate a CFC to test semantics.
    c_target = Commit(repository_id=repo.id, sha="target", message="target", author_name="test", author_email="test", committed_at=base_time + timedelta(days=20))
    db.add(c_target)
    db.flush()
    db.add(CommitFileChange(commit_id=c_target.id, path="dir1/file_a.py", change_type="modified"))
    db.add(CommitFileChange(commit_id=c_target.id, path="dir1/file_a.py", change_type="renamed")) # duplicate path!
    db.add(CommitFileChange(commit_id=c_target.id, path="dir2/file_c.py", change_type="added"))
    db.commit()

    # Set up Repo B
    cb_target = Commit(repository_id=repo_b.id, sha="target_b", message="target b", author_name="test", author_email="test", committed_at=base_time + timedelta(days=20))
    db.add(cb_target)
    db.flush()
    db.add(CommitFileChange(commit_id=cb_target.id, path="dir1/file_a.py", change_type="modified"))
    db.commit()

    yield db
    db.close()

def test_baseline_features_unchanged(setup_db):
    db = setup_db
    c_target = db.query(Commit).filter(Commit.sha == "target").first()
    f = extract_features(db, c_target.id, feature_set="baseline")

    assert set(f.keys()) == set(BASELINE_FEATURES)
    # files_changed counts rows, so 3 changes total
    assert f["files_changed"] == 3
    assert f["prior_change_count"] == 14

def test_expanded_features_correctness(setup_db):
    db = setup_db
    c_target = db.query(Commit).filter(Commit.sha == "target").first()
    f = extract_features(db, c_target.id, feature_set="expanded")

    # 2 distinct directories: dir1 and dir2
    assert f["distinct_directories_touched"] == 2

    # Even though file_a is changed twice in target, distinct paths in dir1 = 1
    assert f["maximum_files_in_single_directory"] == 1

    # files_changed = 3
    # prior file churn = 14
    # avg churn = 14 / 3 = 4.6666...
    assert abs(f["average_prior_file_churn"] - (14 / 3)) < 1e-6
    assert f["maximum_prior_file_churn"] == 14
    assert f["files_with_high_prior_churn"] == 1
    assert f["fraction_concentrated_in_most_changed_file"] == 1.0
    assert abs(f["fraction_of_changed_files_with_high_prior_churn"] - (1 / 3)) < 1e-6

def test_repository_isolation(setup_db):
    db = setup_db
    cb_target = db.query(Commit).filter(Commit.sha == "target_b").first()
    f_before = extract_features(db, cb_target.id, feature_set="expanded")

    assert f_before["repository_prior_commit_count"] == 0
    assert f_before["prior_change_count"] == 0

    # Add massive historical activity to Repo A for the same path and same time window
    repo_a = db.query(Repository).filter(Repository.url == "https://github.com/test/features").first()
    cb_hist = Commit(repository_id=repo_a.id, sha="hist_a", message="hist a", author_name="test", author_email="test", committed_at=cb_target.committed_at - timedelta(days=5))
    db.add(cb_hist)
    db.flush()
    for _ in range(20):
        db.add(CommitFileChange(commit_id=cb_hist.id, path="dir1/file_a.py", change_type="modified"))
    db.commit()

    f_after = extract_features(db, cb_target.id, feature_set="expanded")
    assert f_before == f_after

def test_repeated_extraction_idempotent(setup_db):
    db = setup_db
    c_target = db.query(Commit).filter(Commit.sha == "target").first()

    f1 = extract_features(db, c_target.id, feature_set="expanded")
    f2 = extract_features(db, c_target.id, feature_set="expanded")
    f3 = extract_features(db, c_target.id, feature_set="expanded")

    assert f1 == f2
    assert f2 == f3

def test_finite_values(setup_db):
    db = setup_db
    # Test with substantial history
    c_target = db.query(Commit).filter(Commit.sha == "target").first()
    f_hist = extract_features(db, c_target.id, feature_set="expanded")
    for k in ALL_FEATURES:
        assert k in f_hist
        assert f_hist[k] is not None
        assert math.isfinite(float(f_hist[k]))

    # Test with zero history
    c_init = db.query(Commit).filter(Commit.sha == "c1").first()
    f_zero = extract_features(db, c_init.id, feature_set="expanded")
    for k in ALL_FEATURES:
        assert k in f_zero
        assert f_zero[k] is not None
        assert math.isfinite(float(f_zero[k]))
