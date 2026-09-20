from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from models import File, Commit, CommitFileChange, Repository
from fastapi import HTTPException
from schemas import HistoricalImpactResponse, HistoryCommit, CoChangeNode

def get_historical_impact(db: Session, repo_id: int, path: str, limit: int = 10) -> HistoricalImpactResponse:
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    normalized_forward = path.replace("\\", "/")
    normalized_back = path.replace("/", "\\")

    target_file = db.query(File).filter(
        File.repository_id == repo_id,
        File.path.in_([normalized_forward, normalized_back])
    ).first()

    if not target_file:
        raise HTTPException(status_code=404, detail="File not found")

    # Get bounds
    bounds = db.query(
        func.min(Commit.committed_at),
        func.max(Commit.committed_at)
    ).join(CommitFileChange, Commit.id == CommitFileChange.commit_id)\
     .filter(CommitFileChange.file_id == target_file.id).first()
     
    first_commit_date = bounds[0] if bounds else None
    last_commit_date = bounds[1] if bounds else None

    # Get recent changes
    changes_query = db.query(CommitFileChange, Commit).join(Commit, CommitFileChange.commit_id == Commit.id)\
        .filter(CommitFileChange.file_id == target_file.id)
        
    total_changes = changes_query.count()
    recent = changes_query.order_by(desc(Commit.committed_at), Commit.id).limit(limit).all()
    
    recent_commits = []
    for cfc, commit in recent:
        recent_commits.append(HistoryCommit(
            sha=commit.sha,
            author_name=commit.author_name,
            message=commit.message,
            committed_at=commit.committed_at,
            change_type=cfc.change_type,
            previous_path=cfc.previous_path
        ))
        
    # Co-changes
    target_commit_ids = db.query(CommitFileChange.commit_id).filter(CommitFileChange.file_id == target_file.id)
    
    co_changes_query = db.query(
        CommitFileChange.file_id,
        File.path,
        func.count(CommitFileChange.id).label("shared_commits")
    ).join(File, CommitFileChange.file_id == File.id)\
     .filter(CommitFileChange.commit_id.in_(target_commit_ids))\
     .filter(CommitFileChange.file_id != target_file.id)\
     .filter(File.repository_id == repo_id)\
     .group_by(CommitFileChange.file_id, File.path)\
     .order_by(desc("shared_commits"), File.path)\
     .limit(limit)\
     .all()
     
    co_changes = []
    for row in co_changes_query:
        co_changes.append(CoChangeNode(
            file_id=row.file_id,
            path=row.path,
            shared_commits=row.shared_commits
        ))
        
    return HistoricalImpactResponse(
        repository_id=repo_id,
        target={
            "file_id": target_file.id,
            "path": target_file.path
        },
        total_changes=total_changes,
        first_commit_date=first_commit_date,
        last_commit_date=last_commit_date,
        recent_commits=recent_commits,
        co_changes=co_changes
    )
