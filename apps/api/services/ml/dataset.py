from sqlalchemy.orm import Session
from typing import List, Dict, Any, Tuple
from models import Commit, Repository
from services.ml.labels import get_risk_label
from services.ml.features import extract_features

from datetime import datetime
def build_dataset(db: Session, window_days: int = None, max_timestamp: datetime = None, feature_set: str = "baseline") -> List[Dict[str, Any]]:
    """
    Builds the historical dataset for Phase 6.
    Iterates over all commits in deterministic order (by repository_id, committed_at).
    """
    query = db.query(Commit)
    if max_timestamp is not None:
        query = query.filter(Commit.committed_at < max_timestamp)
    commits = query.order_by(Commit.repository_id, Commit.committed_at).all()
    dataset = []

    for commit in commits:
        label = get_risk_label(db, commit.id, window_days=window_days)
        features = extract_features(db, commit.id, feature_set=feature_set)

        row = {
            "repository_id": commit.repository_id,
            "commit_sha": commit.sha,
            "commit_timestamp": commit.committed_at,
            "risk_label": label
        }
        row.update(features)
        dataset.append(row)

    return dataset

def get_dataset_statistics(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_samples = len(dataset)
    positive = sum(1 for row in dataset if row["risk_label"] == 1)
    negative = sum(1 for row in dataset if row["risk_label"] == 0)
    unlabeled = sum(1 for row in dataset if row["risk_label"] is None)

    repos = len(set(row["repository_id"] for row in dataset))
    timestamps = [row["commit_timestamp"] for row in dataset]

    shas = [(row["repository_id"], row["commit_sha"]) for row in dataset]
    duplicates = total_samples - len(set(shas))

    missing_values = 0
    for row in dataset:
        for k, v in row.items():
            if v is None and k != "risk_label":
                missing_values += 1

    return {
        "total_samples": total_samples,
        "positive_labels": positive,
        "negative_labels": negative,
        "unlabeled": unlabeled,
        "positive_label_ratio": positive / (positive + negative) if (positive + negative) > 0 else 0.0,
        "missing_values": missing_values,
        "duplicate_commits": duplicates,
        "repositories_represented": repos,
        "earliest_timestamp": min(timestamps).isoformat() if timestamps else None,
        "latest_timestamp": max(timestamps).isoformat() if timestamps else None,
    }

def validate_dataset(stats: Dict[str, Any]) -> Tuple[bool, str]:
    if stats["missing_values"] > 0:
        return False, f"Dataset has {stats['missing_values']} missing values"
    if stats["duplicate_commits"] > 0:
        return False, f"Dataset has {stats['duplicate_commits']} duplicate commits"

    if stats["total_samples"] < 100:
        return False, f"Dataset insufficient for training: samples = {stats['total_samples']} (minimum 100 required)"
    if stats["positive_labels"] < 10:
        return False, f"Dataset insufficient for training: positive labels = {stats['positive_labels']} (minimum 10 required)"

    return True, "Dataset is valid and eligible for training"
