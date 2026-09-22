import pytest
from datetime import datetime, UTC
from typing import List, Dict, Any
from services.ml.model import run_model_pipeline, prepare_training_data, split_chronologically
from services.ml.features import BASELINE_FEATURES, ALL_FEATURES

def create_mock_expanded_dataset(n: int = 120) -> List[Dict[str, Any]]:
    dataset = []
    base_time = datetime(2025, 1, 1, tzinfo=UTC)
    for i in range(n):
        # 1/4 positive ratio
        label = 1 if i % 4 == 0 else 0
        row = {
            "repository_id": 1 if i % 2 == 0 else 2,
            "commit_sha": f"sha_{i}",
            "commit_timestamp": base_time,
            "risk_label": label
        }
        # Populate all 15 features with mock data
        for f in ALL_FEATURES:
            row[f] = float(i % 10)
        dataset.append(row)
    return dataset

def test_controlled_evaluation_identical_split():
    dataset = create_mock_expanded_dataset(120)

    # Run Baseline
    res_base = run_model_pipeline(dataset, class_weight="balanced", feature_list=BASELINE_FEATURES)
    # Run Expanded
    res_exp = run_model_pipeline(dataset, class_weight="balanced", feature_list=ALL_FEATURES)

    # Assert identical split
    assert res_base["split_timestamp"] == res_exp["split_timestamp"]
    assert res_base["train_size"] == res_exp["train_size"]
    assert res_base["test_size"] == res_exp["test_size"]

    # Assert same label distributions
    assert res_base["train_positives"] == res_exp["train_positives"]
    assert res_base["train_negatives"] == res_exp["train_negatives"]
    assert res_base["test_positives"] == res_exp["test_positives"]
    assert res_base["test_negatives"] == res_exp["test_negatives"]

    # Assert configuration matches expectations
    assert len(res_base["configuration"]["features"]) == 7
    assert len(res_exp["configuration"]["features"]) == 15
    assert res_base["configuration"]["model"] == res_exp["configuration"]["model"]
    assert res_base["configuration"]["preprocessing"] == res_exp["configuration"]["preprocessing"]

    # Assert metrics are finite
    assert isinstance(res_exp["metrics"]["roc_auc"], float)
