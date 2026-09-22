from datetime import datetime, timedelta, UTC

import pytest
from fastapi.testclient import TestClient

from main import app
from models import (
    Chunk,
    Commit,
    CommitFileChange,
    Dependency,
    File,
    Repository,
    RepositoryStatus,
    Symbol,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db(db_session):
    db = db_session

    # Clean up existing data in FK-safe dependency order.
    db.query(Dependency).delete()
    db.query(Chunk).delete()
    db.query(Symbol).delete()
    db.query(CommitFileChange).delete()
    db.query(Commit).delete()
    db.query(File).delete()
    db.query(Repository).delete()
    db.commit()

    repo = Repository(
        url="https://github.com/test/pred",
        status=RepositoryStatus.completed,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(repo)

    repo2 = Repository(
        url="https://github.com/test/other",
        status=RepositoryStatus.completed,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.add(repo2)
    db.commit()

    base_time = datetime(2020, 1, 1, tzinfo=UTC)

    for i in range(150):
        msg = "Fix something" if i % 30 == 1 else f"Commit {i}"

        commit = Commit(
            repository_id=repo.id,
            sha=f"sha_{i}",
            message=msg,
            author_name="Test",
            author_email="test@test.com",
            committed_at=base_time + timedelta(days=i),
        )
        db.add(commit)
        db.flush()

        db.add(
            CommitFileChange(
                commit_id=commit.id,
                path="main.py",
                change_type="modified",
            )
        )

    db.commit()
    yield


def test_prediction_success_and_shape(db_session):
    repo = db_session.query(Repository).filter_by(
        url="https://github.com/test/pred"
    ).first()

    res = client.get(
        f"/repositories/{repo.id}/risk/predict/sha_149"
    )

    assert res.status_code == 200

    data = res.json()

    assert "proxy_risk_score" in data
    assert 0 <= data["proxy_risk_score"] <= 1
    assert data["model"]["name"] == "logistic_regression"


def test_prediction_404_repo(db_session):
    res = client.get("/repositories/9999/risk/predict/sha_149")

    assert res.status_code == 404


def test_prediction_404_commit(db_session):
    repo = db_session.query(Repository).filter_by(
        url="https://github.com/test/pred"
    ).first()

    res = client.get(
        f"/repositories/{repo.id}/risk/predict/sha_999"
    )

    assert res.status_code == 404


def test_prediction_wrong_repo(db_session):
    repo2 = db_session.query(Repository).filter_by(
        url="https://github.com/test/other"
    ).first()

    res = client.get(
        f"/repositories/{repo2.id}/risk/predict/sha_149"
    )

    assert res.status_code == 404


def test_prediction_deterministic(db_session):
    repo = db_session.query(Repository).filter_by(
        url="https://github.com/test/pred"
    ).first()

    res1 = client.get(
        f"/repositories/{repo.id}/risk/predict/sha_149"
    ).json()

    res2 = client.get(
        f"/repositories/{repo.id}/risk/predict/sha_149"
    ).json()

    assert res1["proxy_risk_score"] == res2["proxy_risk_score"]
    assert res1["features"] == res2["features"]


def test_prediction_temporal_rule(db_session):
    repo = db_session.query(Repository).filter_by(
        url="https://github.com/test/pred"
    ).first()

    res = client.get(
        f"/repositories/{repo.id}/risk/predict/sha_50"
    )

    assert res.status_code == 400
    assert "Insufficient historical data" in res.json()["detail"]


def test_prediction_no_future_leakage(db_session):
    repo = db_session.query(Repository).filter_by(
        url="https://github.com/test/pred"
    ).first()

    res_before = client.get(
        f"/repositories/{repo.id}/risk/predict/sha_140"
    ).json()

    commit = db_session.query(Commit).filter(
        Commit.sha == "sha_145"
    ).first()

    for i in range(100):
        db_session.add(
            CommitFileChange(
                commit_id=commit.id,
                path=f"new_file_{i}.py",
                change_type="added",
            )
        )

    db_session.commit()

    res_after = client.get(
        f"/repositories/{repo.id}/risk/predict/sha_140"
    ).json()

    assert res_before["proxy_risk_score"] == res_after["proxy_risk_score"]
    assert res_before["features"] == res_after["features"]


def test_prediction_db_integrity(db_session):
    repo = db_session.query(Repository).filter_by(
        url="https://github.com/test/pred"
    ).first()

    repo_count = db_session.query(Repository).count()
    commit_count = db_session.query(Commit).count()
    cfc_count = db_session.query(CommitFileChange).count()

    res = client.get(
        f"/repositories/{repo.id}/risk/predict/sha_149"
    )

    assert res.status_code == 200

    assert db_session.query(Repository).count() == repo_count
    assert db_session.query(Commit).count() == commit_count
    assert db_session.query(CommitFileChange).count() == cfc_count


def test_one_class_history(db_session):
    repo = db_session.query(Repository).filter_by(
        url="https://github.com/test/pred"
    ).first()

    for i in range(150):
        if i % 30 == 1:
            commit = db_session.query(Commit).filter(
                Commit.sha == f"sha_{i}"
            ).first()
            commit.message = "Nothing to see here"

    db_session.commit()

    res = client.get(
        f"/repositories/{repo.id}/risk/predict/sha_140"
    )

    assert res.status_code == 400
    assert "Insufficient" in res.json()["detail"]


def test_api_service_consistency(db_session):
    repo = db_session.query(Repository).filter_by(
        url="https://github.com/test/pred"
    ).first()

    commit = db_session.query(Commit).filter(
        Commit.repository_id == repo.id,
        Commit.sha == "sha_149",
    ).first()

    from services.ml.prediction import predict_proxy_risk_score

    direct_res = predict_proxy_risk_score(
        db_session,
        repo.id,
        commit.sha,
    )

    api_res = client.get(
        f"/repositories/{repo.id}/risk/predict/{commit.sha}"
    ).json()

    assert direct_res["proxy_risk_score"] == api_res["proxy_risk_score"]
    assert direct_res["features"] == api_res["features"]
    assert direct_res["model"] == api_res["model"]


def test_cross_repository_training(db_session):
    repo1 = db_session.query(Repository).filter_by(
        url="https://github.com/test/pred"
    ).first()

    repo2 = db_session.query(Repository).filter_by(
        url="https://github.com/test/other"
    ).first()

    # Target commit in repo 2 is strictly later than repo 1 history.
    base_time = datetime(2025, 1, 1, tzinfo=UTC)

    target = Commit(
        repository_id=repo2.id,
        sha="repo2_target",
        message="target",
        author_name="Test",
        author_email="test@test.com",
        committed_at=base_time,
    )

    db_session.add(target)
    db_session.flush()

    db_session.add(
        CommitFileChange(
            commit_id=target.id,
            path="main.py",
            change_type="modified",
        )
    )

    db_session.commit()

    # Repo 1 provides historical training data before the target.
    res = client.get(
        f"/repositories/{repo2.id}/risk/predict/repo2_target"
    )

    assert res.status_code == 200
    assert res.json()["repository_id"] == repo2.id


def test_prediction_feature_set(db_session):
    repo = db_session.query(Repository).filter_by(
        url="https://github.com/test/pred"
    ).first()

    res = client.get(
        f"/repositories/{repo.id}/risk/predict/sha_149?feature_set=expanded"
    )

    assert res.status_code == 200

    data = res.json()

    assert len(data["features"]) > 7
    assert "distinct_directories_touched" in data["features"]
