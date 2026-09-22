import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, average_precision_score, brier_score_loss
from typing import List, Dict, Any, Tuple, Optional
from services.ml.features import BASELINE_FEATURES

# Ensure backwards compatibility for external imports
FEATURES = BASELINE_FEATURES

def prepare_training_data(dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered = [row for row in dataset if row["risk_label"] in (0, 1)]
    filtered.sort(key=lambda x: x["commit_timestamp"])
    return filtered

def split_chronologically(labeled_data: List[Dict[str, Any]], train_ratio: float = 0.8) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    if not labeled_data:
        return [], [], None
    n = len(labeled_data)
    train_size = int(n * train_ratio)
    train_data = labeled_data[:train_size]
    test_data = labeled_data[train_size:]
    split_timestamp = test_data[0]["commit_timestamp"].isoformat() if test_data else None
    return train_data, test_data, split_timestamp

def extract_matrix(data: List[Dict[str, Any]], feature_list: List[str] = BASELINE_FEATURES) -> Tuple[np.ndarray, np.ndarray]:
    X = np.array([[float(row[f]) for f in feature_list] for row in data])
    y = np.array([int(row["risk_label"]) for row in data])
    return X, y

def get_class_distribution(y: np.ndarray) -> Dict[str, float]:
    total = len(y)
    if total == 0:
        return {"positive_ratio": 0.0, "negative_ratio": 0.0, "positives": 0, "negatives": 0}
    pos = np.sum(y)
    return {
        "positive_ratio": pos / total,
        "negative_ratio": (total - pos) / total,
        "positives": pos,
        "negatives": total - pos
    }

def get_calibration_stats(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> List[Dict[str, Any]]:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    binids = np.digitize(y_prob, bins) - 1

    calibration = []
    for i in range(n_bins):
        bin_idx = binids == i
        count = int(np.sum(bin_idx))
        if count > 0:
            mean_pred = float(np.mean(y_prob[bin_idx]))
            observed_pos = float(np.mean(y_true[bin_idx]))
        else:
            mean_pred = None
            observed_pos = None

        calibration.append({
            "bin_lower": float(bins[i]),
            "bin_upper": float(bins[i+1]),
            "count": count,
            "mean_predicted_probability": mean_pred,
            "observed_positive_rate": observed_pos
        })
    return calibration

def train_baseline(train_data: List[Dict[str, Any]], class_weight: Optional[str] = "balanced", feature_list: List[str] = BASELINE_FEATURES) -> Pipeline:
    X_train, y_train = extract_matrix(train_data, feature_list)
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("logreg", LogisticRegression(max_iter=1000, random_state=42, class_weight=class_weight))
    ])
    pipeline.fit(X_train, y_train)
    return pipeline

def evaluate_baseline(pipeline: Pipeline, test_data: List[Dict[str, Any]], feature_list: List[str] = BASELINE_FEATURES) -> Dict[str, Any]:
    X_test, y_test = extract_matrix(test_data, feature_list)
    if len(y_test) == 0:
        return {}

    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1] if len(pipeline.classes_) == 2 else None

    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0)
    }

    if y_prob is not None and len(np.unique(y_test)) == 2:
        metrics["roc_auc"] = roc_auc_score(y_test, y_prob)
        metrics["pr_auc"] = average_precision_score(y_test, y_prob)
        metrics["brier_score"] = brier_score_loss(y_test, y_prob)

        metrics["prob_min"] = float(np.min(y_prob))
        metrics["prob_max"] = float(np.max(y_prob))
        metrics["prob_mean"] = float(np.mean(y_prob))
        metrics["prob_median"] = float(np.median(y_prob))
        metrics["actual_positive_rate"] = float(np.mean(y_test))
        metrics["calibration_bins"] = get_calibration_stats(y_test, y_prob, 10)
    else:
        for k in ["roc_auc", "pr_auc", "brier_score", "prob_min", "prob_max", "prob_mean", "prob_median", "actual_positive_rate", "calibration_bins"]:
            metrics[k] = "unavailable"

    cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
    metrics["confusion_matrix"] = {
        "true_negatives": int(cm[0, 0]),
        "false_positives": int(cm[0, 1]),
        "false_negatives": int(cm[1, 0]),
        "true_positives": int(cm[1, 1])
    }

    model = pipeline.named_steps["logreg"]
    coefs = model.coef_[0]
    metrics["coefficients"] = {feat: float(coef) for feat, coef in zip(feature_list, coefs)}
    return metrics

def run_model_pipeline(dataset: List[Dict[str, Any]], class_weight: Optional[str] = "balanced", feature_list: List[str] = BASELINE_FEATURES) -> Dict[str, Any]:
    from services.ml.dataset import get_dataset_statistics, validate_dataset
    stats = get_dataset_statistics(dataset)
    valid, msg = validate_dataset(stats)
    if not valid:
        raise ValueError(f"Dataset ineligible for training: {msg}")

    labeled_data = prepare_training_data(dataset)
    train_data, test_data, split_timestamp = split_chronologically(labeled_data)
    X_train, y_train = extract_matrix(train_data, feature_list)
    if len(np.unique(y_train)) < 2:
        raise ValueError("Training dataset must contain both classes.")

    pipeline = train_baseline(train_data, class_weight=class_weight, feature_list=feature_list)
    metrics = evaluate_baseline(pipeline, test_data, feature_list=feature_list)

    train_dist = get_class_distribution(y_train)
    _, y_test = extract_matrix(test_data, feature_list)
    test_dist = get_class_distribution(y_test)

    return {
        "split_timestamp": split_timestamp,
        "train_size": len(train_data),
        "test_size": len(test_data),
        "train_positives": int(train_dist["positives"]),
        "train_negatives": int(train_dist["negatives"]),
        "test_positives": int(test_dist["positives"]),
        "test_negatives": int(test_dist["negatives"]),
        "metrics": metrics,
        "configuration": {
            "model": f"LogisticRegression(max_iter=1000, random_state=42, class_weight={repr(class_weight)})",
            "preprocessing": "StandardScaler()",
            "features": feature_list,
            "train_ratio": 0.8
        }
    }

def run_baseline_audit(dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
    res_none = run_model_pipeline(dataset, class_weight=None)
    res_balanced = run_model_pipeline(dataset, class_weight="balanced")

    labeled_data = prepare_training_data(dataset)
    _, test_data, _ = split_chronologically(labeled_data)

    repo_dist = {}
    for row in test_data:
        rid = row["repository_id"]
        repo_dist.setdefault(rid, {"total": 0, "positives": 0, "negatives": 0})
        repo_dist[rid]["total"] += 1
        if row["risk_label"] == 1:
            repo_dist[rid]["positives"] += 1
        else:
            repo_dist[rid]["negatives"] += 1

    for rid, counts in repo_dist.items():
        counts["positive_ratio"] = counts["positives"] / counts["total"]

    return {
        "class_weight_none": res_none,
        "class_weight_balanced": res_balanced,
        "test_repository_distribution": repo_dist
    }
