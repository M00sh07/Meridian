from typing import Dict, Any
from sqlalchemy.orm import Session
from models import Commit, Repository
from services.ml.features import extract_features
from services.ml.dataset import build_dataset, get_dataset_statistics, validate_dataset
from services.ml.model import prepare_training_data, train_baseline, FEATURES
import numpy as np

class PredictionError(Exception):
    pass

def predict_proxy_risk_score(db: Session, repo_id: int, commit_sha: str, feature_set: str = "baseline") -> Dict[str, Any]:
    from services.ml.features import BASELINE_FEATURES, ALL_FEATURES

    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise PredictionError('Repository not found')

    commit = db.query(Commit).filter(Commit.repository_id == repo_id, Commit.sha == commit_sha).first()
    if not commit:
        raise PredictionError('Commit not found in this repository')

    if feature_set == "expanded":
        feature_list = ALL_FEATURES
        version = 'expanded-v1'
    else:
        feature_list = BASELINE_FEATURES
        version = 'baseline-v1'

    features_dict = extract_features(db, commit.id, feature_set=feature_set)

    historical_dataset = build_dataset(db, max_timestamp=commit.committed_at, feature_set=feature_set)

    stats = get_dataset_statistics(historical_dataset)
    valid, msg = validate_dataset(stats)
    if not valid:
        raise PredictionError(f'Insufficient historical data for prediction: {msg}')

    train_data = prepare_training_data(historical_dataset)
    labels = [row['risk_label'] for row in train_data]
    if len(set(labels)) < 2:
        raise PredictionError('Insufficient historical data: Training dataset must contain both positive and negative classes.')

    pipeline = train_baseline(train_data, class_weight='balanced', feature_list=feature_list)

    X_target = np.array([[float(features_dict[f]) for f in feature_list]])

    proxy_risk_score = float(pipeline.predict_proba(X_target)[0, 1])

    return {
        'repository_id': repo_id,
        'commit_sha': commit_sha,
        'proxy_risk_score': proxy_risk_score,
        'model': {
            'name': 'logistic_regression',
            'version': version,
            'class_weight': 'balanced',
            'features': feature_list
        },
        'features': {f: features_dict[f] for f in feature_list},
        'label_definition': 'historical corrective-commit proxy'
    }
