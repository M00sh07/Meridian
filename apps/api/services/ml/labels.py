import os
import re
from datetime import timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from models import Commit, CommitFileChange

RISK_LABEL_WINDOW_DAYS = int(os.getenv("RISK_LABEL_WINDOW_DAYS", "14"))

CORRECTIVE_PATTERN = re.compile(r"\b(fix|fixes|fixed|revert|reverts|hotfix|patch)\b", re.IGNORECASE)

def is_corrective_message(message: str) -> bool:
    if not message:
        return False
    return bool(CORRECTIVE_PATTERN.search(message))

def get_risk_label(db: Session, commit_id: int, window_days: int = None) -> Optional[int]:
    """
    Returns 1 if the commit has historical evidence of being problematic,
    0 if there is enough historical window to observe no issues,
    None if the window has not yet passed and no evidence was found (insufficient evidence).
    """
    if window_days is None:
        window_days = RISK_LABEL_WINDOW_DAYS

    commit = db.query(Commit).filter(Commit.id == commit_id).first()
    if not commit:
        return None

    # Get paths touched by this commit
    changes = db.query(CommitFileChange).filter(CommitFileChange.commit_id == commit_id).all()
    if not changes:
        return 0

    paths = {c.path for c in changes if c.path}

    # Find subsequent commits within the window
    window_end = commit.committed_at + timedelta(days=window_days)

    subsequent_commits = db.query(Commit).filter(
        Commit.repository_id == commit.repository_id,
        Commit.committed_at > commit.committed_at,
        Commit.committed_at <= window_end
    ).all()

    for sc in subsequent_commits:
        if is_corrective_message(sc.message):
            # Did it touch any of the same paths?
            sc_changes = db.query(CommitFileChange).filter(CommitFileChange.commit_id == sc.id).all()
            sc_paths = {c.path for c in sc_changes if c.path}
            if not paths.isdisjoint(sc_paths):
                return 1

    # If we get here, no corrective commit was found in the window.
    latest_repo_commit = db.query(Commit).filter(
        Commit.repository_id == commit.repository_id
    ).order_by(Commit.committed_at.desc()).first()

    if latest_repo_commit and latest_repo_commit.committed_at >= window_end:
        return 0

    return None
