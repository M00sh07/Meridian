import os
import re
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from models import Commit, CommitFileChange
from typing import Dict, Any
from collections import defaultdict

BASELINE_FEATURES = [
    "files_changed",
    "files_added",
    "files_modified",
    "files_deleted",
    "files_renamed",
    "prior_change_count",
    "recent_prior_change_count"
]

HISTORICAL_FEATURES = [
    "distinct_directories_touched",
    "maximum_files_in_single_directory",
    "average_prior_file_churn",
    "maximum_prior_file_churn",
    "files_with_high_prior_churn",
    "fraction_concentrated_in_most_changed_file",
    "fraction_of_changed_files_with_high_prior_churn",
    "repository_prior_commit_count"
]

ALL_FEATURES = BASELINE_FEATURES + HISTORICAL_FEATURES
HIGH_CHURN_THRESHOLD = 10

def extract_features(db: Session, commit_id: int, feature_set: str = "baseline") -> Dict[str, Any]:
    """
    Extracts features for a given commit.
    Strictly leakage-safe: only uses data from the commit itself or prior commits.
    """
    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        return {}

    changes = db.query(CommitFileChange).filter(CommitFileChange.commit_id == commit_id).all()

    files_added = 0
    files_modified = 0
    files_deleted = 0
    files_renamed = 0
    paths = set()

    for c in changes:
        if c.path:
            paths.add(c.path)
        if c.change_type == "added":
            files_added += 1
        elif c.change_type == "modified":
            files_modified += 1
        elif c.change_type == "deleted":
            files_deleted += 1
        elif c.change_type == "renamed":
            files_renamed += 1

    files_changed = len(changes)

    # Baseline History: Prior changes to the same files
    prior_change_count = 0
    recent_prior_change_count = 0
    prior_changes = []

    if paths:
        thirty_days_ago = commit.committed_at - timedelta(days=30)

        prior_changes = db.query(CommitFileChange).join(Commit).filter(
            Commit.repository_id == commit.repository_id,
            Commit.committed_at < commit.committed_at,
            CommitFileChange.path.in_(paths)
        ).all()

        prior_change_count = len(prior_changes)
        recent_prior_change_count = sum(1 for pc in prior_changes if pc.commit.committed_at >= thirty_days_ago)

    features = {
        "files_changed": files_changed,
        "files_added": files_added,
        "files_modified": files_modified,
        "files_deleted": files_deleted,
        "files_renamed": files_renamed,
        "prior_change_count": prior_change_count,
        "recent_prior_change_count": recent_prior_change_count
    }

    if feature_set == "expanded":
        distinct_dirs = defaultdict(set)
        for p in paths:
            d = os.path.dirname(p)
            distinct_dirs[d].add(p)

        distinct_directories_touched = len(distinct_dirs)
        maximum_files_in_single_directory = max((len(s) for s in distinct_dirs.values()), default=0)

        file_churns = defaultdict(int)
        for pc in prior_changes:
            file_churns[pc.path] += 1

        sum_churn = sum(file_churns.values())
        max_churn = max(file_churns.values()) if file_churns else 0
        avg_churn = sum_churn / files_changed if files_changed > 0 else 0
        files_high_churn = sum(1 for count in file_churns.values() if count > HIGH_CHURN_THRESHOLD)

        features["distinct_directories_touched"] = distinct_directories_touched
        features["maximum_files_in_single_directory"] = maximum_files_in_single_directory
        features["average_prior_file_churn"] = float(avg_churn)
        features["maximum_prior_file_churn"] = max_churn
        features["files_with_high_prior_churn"] = files_high_churn
        features["fraction_concentrated_in_most_changed_file"] = float(max_churn / sum_churn) if sum_churn > 0 else 0.0
        features["fraction_of_changed_files_with_high_prior_churn"] = float(files_high_churn / files_changed) if files_changed > 0 else 0.0

        repo_commits = db.query(Commit).filter(
            Commit.repository_id == commit.repository_id,
            Commit.committed_at < commit.committed_at
        ).count()
        features["repository_prior_commit_count"] = repo_commits

    return features
