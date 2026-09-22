from datetime import timedelta
import pytest
from models import Commit, CommitFileChange, Repository
from services.ml.labels import get_risk_label
from services.ml.features import extract_features
from services.ml.dataset import build_dataset, get_dataset_statistics, validate_dataset
from database import Base

def test_features_leakage_and_logic(db_session):
    repo = Repository(url="https://github.com/test/ml", status="completed")
    db_session.add(repo)
    db_session.commit()
    t1 = repo.created_at
    c1 = Commit(repository_id=repo.id, sha="111", message="init", committed_at=t1)
    db_session.add(c1)
    db_session.commit()
    cf1 = CommitFileChange(commit_id=c1.id, path="a.py", change_type="added")
    db_session.add(cf1)
    db_session.commit()
    f1 = extract_features(db_session, c1.id)
    assert f1["files_changed"] == 1
    assert f1["files_added"] == 1
    assert f1["prior_change_count"] == 0
    t2 = t1 + timedelta(days=5)
    c2 = Commit(repository_id=repo.id, sha="222", message="update", committed_at=t2)
    db_session.add(c2)
    db_session.commit()
    cf2 = CommitFileChange(commit_id=c2.id, path="a.py", change_type="modified")
    db_session.add(cf2)
    db_session.commit()
    f2 = extract_features(db_session, c2.id)
    assert f2["files_changed"] == 1
    assert f2["files_modified"] == 1
    assert f2["prior_change_count"] == 1
    f1_again = extract_features(db_session, c1.id)
    assert f1_again["prior_change_count"] == 0

def test_labels_corrective_commit(db_session):
    repo = Repository(url="https://github.com/test/ml2", status="completed")
    db_session.add(repo)
    db_session.commit()
    t1 = repo.created_at
    c1 = Commit(repository_id=repo.id, sha="111", message="feature", committed_at=t1)
    db_session.add(c1)
    db_session.commit()
    cf1 = CommitFileChange(commit_id=c1.id, path="a.py", change_type="added")
    db_session.add(cf1)
    t2 = t1 + timedelta(days=2)
    c2 = Commit(repository_id=repo.id, sha="222", message="fix bug in a", committed_at=t2)
    db_session.add(c2)
    db_session.commit()
    cf2 = CommitFileChange(commit_id=c2.id, path="a.py", change_type="modified")
    db_session.add(cf2)
    db_session.commit()
    label1 = get_risk_label(db_session, c1.id, window_days=14)
    assert label1 == 1
    label2 = get_risk_label(db_session, c2.id, window_days=14)
    assert label2 is None

def test_labels_negative_no_fix(db_session):
    repo = Repository(url="https://github.com/test/ml3", status="completed")
    db_session.add(repo)
    db_session.commit()
    t1 = repo.created_at
    c1 = Commit(repository_id=repo.id, sha="111", message="feature", committed_at=t1)
    db_session.add(c1)
    db_session.commit()
    cf1 = CommitFileChange(commit_id=c1.id, path="a.py", change_type="added")
    db_session.add(cf1)
    t2 = t1 + timedelta(days=20)
    c2 = Commit(repository_id=repo.id, sha="222", message="unrelated", committed_at=t2)
    db_session.add(c2)
    db_session.commit()
    label1 = get_risk_label(db_session, c1.id, window_days=14)
    assert label1 == 0

def test_dataset_reproducibility(db_session):
    repo = Repository(url="https://github.com/test/ml4", status="completed")
    db_session.add(repo)
    db_session.commit()
    c1 = Commit(repository_id=repo.id, sha="111", message="init", committed_at=repo.created_at)
    db_session.add(c1)
    db_session.commit()
    ds1 = build_dataset(db_session)
    ds2 = build_dataset(db_session)
    assert ds1 == ds2
    stats = get_dataset_statistics(ds1)
    assert stats["duplicate_commits"] == 0
    assert stats["missing_values"] == 0
    valid, msg = validate_dataset(stats)
    assert valid is False
    assert "insufficient" in msg.lower()

def test_configurable_label_window(db_session, monkeypatch):
    import os
    monkeypatch.setenv("RISK_LABEL_WINDOW_DAYS", "5")
    from services.ml import labels
    monkeypatch.setattr(labels, "RISK_LABEL_WINDOW_DAYS", 5)
    repo = Repository(url="https://github.com/test/window", status="completed")
    db_session.add(repo)
    db_session.commit()
    t1 = repo.created_at
    c1 = Commit(repository_id=repo.id, sha="win1", message="feature", committed_at=t1)
    db_session.add(c1)
    db_session.commit()
    cf1 = CommitFileChange(commit_id=c1.id, path="win.py", change_type="added")
    db_session.add(cf1)
    t2 = t1 + timedelta(days=10)
    c2 = Commit(repository_id=repo.id, sha="win2", message="fix win", committed_at=t2)
    db_session.add(c2)
    db_session.commit()
    cf2 = CommitFileChange(commit_id=c2.id, path="win.py", change_type="modified")
    db_session.add(cf2)
    t3 = t1 + timedelta(days=20)
    c3 = Commit(repository_id=repo.id, sha="win3", message="unrelated", committed_at=t3)
    db_session.add(c3)
    db_session.commit()
    label_5 = labels.get_risk_label(db_session, c1.id)
    assert label_5 == 0
    label_14 = labels.get_risk_label(db_session, c1.id, window_days=14)
    assert label_14 == 1

def test_label_edge_cases(db_session):
    repo1 = Repository(url="https://github.com/test/edge1", status="completed")
    repo2 = Repository(url="https://github.com/test/edge2", status="completed")
    db_session.add_all([repo1, repo2])
    db_session.commit()

    t0 = repo1.created_at
    c_prev = Commit(repository_id=repo1.id, sha="prev", message="fix edge", committed_at=t0 - timedelta(days=1))
    c_target = Commit(repository_id=repo1.id, sha="target", message="feature", committed_at=t0)

    db_session.add_all([c_prev, c_target])
    db_session.commit()

    for c in [c_prev, c_target]:
        db_session.add(CommitFileChange(commit_id=c.id, path="edge.py", change_type="modified"))

    c_other = Commit(repository_id=repo2.id, sha="other", message="fix edge", committed_at=t0 + timedelta(days=5))
    db_session.add(c_other)
    db_session.commit()
    db_session.add(CommitFileChange(commit_id=c_other.id, path="edge.py", change_type="modified"))
    db_session.commit()

    from services.ml import labels

    # At this point, c_target is the latest commit in repo1.
    assert labels.get_risk_label(db_session, c_target.id, window_days=14) is None

    # Add a commit outside the window (closes the window safely)
    c_latest = Commit(repository_id=repo1.id, sha="latest", message="unrelated", committed_at=t0 + timedelta(days=20))
    db_session.add(c_latest)
    db_session.commit()
    db_session.add(CommitFileChange(commit_id=c_latest.id, path="edge.py", change_type="modified"))
    db_session.commit()

    # Now it should be 0 because c_prev is before and c_other is another repo
    assert labels.get_risk_label(db_session, c_target.id, window_days=14) == 0

    # Add a boundary commit
    c_boundary = Commit(repository_id=repo1.id, sha="bound", message="fix bound", committed_at=t0 + timedelta(days=14))
    db_session.add(c_boundary)
    db_session.commit()
    db_session.add(CommitFileChange(commit_id=c_boundary.id, path="edge.py", change_type="modified"))
    db_session.commit()

    # Now it should be 1
    assert labels.get_risk_label(db_session, c_target.id, window_days=14) == 1

def test_features_strict_leakage(db_session):
    repo = Repository(url="https://github.com/test/leak", status="completed")
    db_session.add(repo)
    db_session.commit()
    t0 = repo.created_at
    c1 = Commit(repository_id=repo.id, sha="leak1", message="init", committed_at=t0)
    db_session.add(c1)
    db_session.commit()
    db_session.add(CommitFileChange(commit_id=c1.id, path="leak.py", change_type="added"))
    db_session.commit()
    f_before = extract_features(db_session, c1.id)
    c2 = Commit(repository_id=repo.id, sha="leak2", message="future", committed_at=t0 + timedelta(days=1))
    db_session.add(c2)
    db_session.commit()
    db_session.add(CommitFileChange(commit_id=c2.id, path="leak.py", change_type="modified"))
    db_session.commit()
    c3 = Commit(repository_id=repo.id, sha="leak3", message="fix leak", committed_at=t0 + timedelta(days=2))
    db_session.add(c3)
    db_session.commit()
    db_session.add(CommitFileChange(commit_id=c3.id, path="leak.py", change_type="modified"))
    db_session.commit()
    repo2 = Repository(url="https://github.com/test/leak2", status="completed")
    db_session.add(repo2)
    db_session.commit()
    c4 = Commit(repository_id=repo2.id, sha="leak4", message="unrelated", committed_at=t0 - timedelta(days=1))
    db_session.add(c4)
    db_session.commit()
    db_session.add(CommitFileChange(commit_id=c4.id, path="leak.py", change_type="modified"))
    db_session.commit()
    f_after = extract_features(db_session, c1.id)
    assert f_before == f_after
    assert f_after["prior_change_count"] == 0
