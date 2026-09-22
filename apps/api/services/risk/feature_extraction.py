from datetime import datetime, timedelta, UTC
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from models import Repository, File, Symbol, Commit, CommitFileChange
from services.impact.dependency_impact import get_dependency_impact
from schemas import RiskFeatureResponse, RiskFeatures

RECENT_WINDOW_DAYS = 30

def get_risk_features(db: Session, repo_id: int, path: str, depth: int = 1) -> RiskFeatureResponse:
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

    # Structural Features
    symbols = db.query(Symbol.type, func.count(Symbol.id)).filter(
        Symbol.file_id == target_file.id
    ).group_by(Symbol.type).all()

    symbol_count = sum(count for _, count in symbols)
    function_count = sum(count for type_, count in symbols if type_ in ("function", "method"))
    class_count = sum(count for type_, count in symbols if type_ == "class")

    # Dependency Features
    dep_impact = get_dependency_impact(db, repo_id, target_file.path, depth)
    direct_dependency_count = len(dep_impact.get("direct_dependencies", []))
    direct_dependent_count = len(dep_impact.get("direct_dependents", []))
    transitive_affected_file_count = dep_impact.get("total_affected", 0)

    # Historical Features
    # Explicitly independent of API pagination limit.
    historical_change_count = db.query(CommitFileChange).filter(
        CommitFileChange.file_id == target_file.id
    ).count()

    recent_cutoff = datetime.now(UTC) - timedelta(days=RECENT_WINDOW_DAYS)
    recent_commit_query = db.query(Commit.id).join(CommitFileChange).filter(
        CommitFileChange.file_id == target_file.id,
        Commit.committed_at >= recent_cutoff
    )

    recent_change_count = recent_commit_query.count()

    co_changed_file_count = db.query(CommitFileChange.file_id).filter(
        CommitFileChange.commit_id.in_(recent_commit_query),
        CommitFileChange.file_id != target_file.id
    ).distinct().count()

    return RiskFeatureResponse(
        repository_id=repo_id,
        target={
            "file_id": target_file.id,
            "path": target_file.path
        },
        features=RiskFeatures(
            symbol_count=symbol_count,
            function_count=function_count,
            class_count=class_count,
            direct_dependency_count=direct_dependency_count,
            direct_dependent_count=direct_dependent_count,
            transitive_affected_file_count=transitive_affected_file_count,
            historical_change_count=historical_change_count,
            recent_change_count=recent_change_count,
            co_changed_file_count=co_changed_file_count
        )
    )

