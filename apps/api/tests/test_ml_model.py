from datetime import datetime, timedelta, UTC
import pytest
import numpy as np
from services.ml.model import (
    prepare_training_data,
    split_chronologically,
    run_model_pipeline,
    run_baseline_audit,
    train_baseline,
    evaluate_baseline,
    get_calibration_stats,
    FEATURES
)

def create_mock_dataset(size, positives):
    data = []
    base_time = datetime(2020, 1, 1, tzinfo=UTC)
    for i in range(size):
        label = 1 if i < positives else 0
        if i == size - 1:
            label = None

        row = {
            "repository_id": 1,
            "commit_sha": f"sha_{i}",
            "commit_timestamp": base_time + timedelta(days=i),
            "risk_label": label
        }
        for f in FEATURES:
            row[f] = float(i % 5)
        data.append(row)
    return data

def test_eligibility_failure():
    data = create_mock_dataset(50, 5)
    with pytest.raises(ValueError, match="Dataset ineligible"):
        run_model_pipeline(data)

def test_unlabeled_exclusion_and_ordering():
    data = create_mock_dataset(150, 20)
    shuffled = data.copy()
    shuffled.reverse()
    labeled = prepare_training_data(shuffled)
    assert len(labeled) == 149
    for i in range(len(labeled) - 1):
        assert labeled[i]["commit_timestamp"] <= labeled[i+1]["commit_timestamp"]

def test_chronological_split():
    data = create_mock_dataset(150, 20)
    labeled = prepare_training_data(data)
    train, test, split_ts = split_chronologically(labeled, train_ratio=0.8)
    assert len(train) == int(149 * 0.8)
    assert len(test) == 149 - len(train)
    assert max(r["commit_timestamp"] for r in train) <= min(r["commit_timestamp"] for r in test)
    assert split_ts == test[0]["commit_timestamp"].isoformat()

def test_pipeline_and_one_class_test_set():
    data = []
    base_time = datetime(2020, 1, 1, tzinfo=UTC)
    for i in range(80):
        row = {"commit_timestamp": base_time + timedelta(days=i), "risk_label": 1 if i % 2 == 0 else 0}
        for f in FEATURES: row[f] = 1.0
        data.append(row)
    for i in range(20):
        row = {"commit_timestamp": base_time + timedelta(days=80+i), "risk_label": 0}
        for f in FEATURES: row[f] = 1.0
        data.append(row)

    labeled = prepare_training_data(data)
    train, test, _ = split_chronologically(labeled, train_ratio=0.8)

    pipeline = train_baseline(train)
    metrics = evaluate_baseline(pipeline, test)

    assert metrics["roc_auc"] == "unavailable"
    assert metrics["pr_auc"] == "unavailable"
    assert metrics["brier_score"] == "unavailable"
    assert metrics["prob_min"] == "unavailable"
    assert metrics["calibration_bins"] == "unavailable"
    assert "coefficients" in metrics

def test_calibration_bin_construction():
    y_true = np.array([0, 0, 1, 1, 0])
    y_prob = np.array([0.1, 0.15, 0.8, 0.9, 0.85]) # The last three are in [0.8, 0.9) and [0.9, 1.0]

    cal = get_calibration_stats(y_true, y_prob, n_bins=10)
    assert len(cal) == 10
    assert cal[1]["count"] == 2
    assert cal[1]["observed_positive_rate"] == 0.0
    assert cal[8]["count"] == 2 # 0.8 and 0.85
    assert cal[8]["observed_positive_rate"] == 0.5
    assert cal[9]["count"] == 1 # 0.9
    assert cal[9]["observed_positive_rate"] == 1.0

def test_reproducibility():
    data = create_mock_dataset(150, 20)
    for i, row in enumerate(data):
        if row["risk_label"] is not None:
            for f in FEATURES:
                row[f] = (i * 7.5) % 13.0

    res1 = run_baseline_audit(data)
    res2 = run_baseline_audit(data)
    assert res1["class_weight_none"]["metrics"] == res2["class_weight_none"]["metrics"]
    assert res1["class_weight_balanced"]["metrics"]["calibration_bins"] == res2["class_weight_balanced"]["metrics"]["calibration_bins"]
