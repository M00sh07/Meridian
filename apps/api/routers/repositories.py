import os
import shutil
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session
from database import get_db
from models import Repository, File, Symbol, Dependency, RepositoryStatus, Commit, CommitFileChange, Chunk
from schemas import (
    RepositoryCreate,
    RepositoryResponse,
    DependencyResponse,
    PaginatedFiles,
    PaginatedSymbols,
    PaginatedCommits,
    CommitChangeResponse,
    PaginatedFileCommits,
    FileChurnResponse,
    FileHotspotResponse,
    PaginatedChunks,
    EmbeddingStatusResponse,
    EmbeddingResultResponse,
    SearchResponse,
    ContextAssemblyResponse,
)
from services.ingestion_job import process_repository
from services.embedding_service import embed_repository_chunks, count_pending_chunks
from services.embedding_config import get_dimension, get_model_name
# Git churn is considered "recent" when it falls inside this window.
HOTSPOT_RECENT_WINDOW_DAYS = 90
router = APIRouter(prefix="/repositories", tags=["repositories"])
@router.get("/", response_model=List[RepositoryResponse])
def list_repositories(db: Session = Depends(get_db)):
    return db.query(Repository).order_by(
        Repository.created_at.desc(), Repository.id.desc()
    ).all()
@router.post("/", response_model=RepositoryResponse)
def create_repository(
    repo_in: RepositoryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    if not repo_in.url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only HTTPS GitHub URLs are supported.")
    # Check if exists
    repo = db.query(Repository).filter(Repository.url == repo_in.url).first()
    if repo:
        if repo.status in [RepositoryStatus.pending, RepositoryStatus.cloning, RepositoryStatus.parsing, RepositoryStatus.completed]:
            return repo
        # If failed, we can restart it.
        repo.status = RepositoryStatus.pending
        db.commit()
    else:
        repo = Repository(url=repo_in.url, status=RepositoryStatus.pending)
        db.add(repo)
        db.commit()
        db.refresh(repo)
    background_tasks.add_task(process_repository, repo.id)
    return repo
@router.get("/{repo_id}", response_model=RepositoryResponse)
def get_repository(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo
@router.get("/{repo_id}/dependencies", response_model=List[DependencyResponse])
def get_repository_dependencies(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    dependencies = (
        db.query(Dependency, File.path)
        .join(File, Dependency.source_file_id == File.id)
        .filter(File.repository_id == repo_id)
        .all()
    )
    return [
        {
            "source_file": source_path,
            "target_file": dependency.target_file.path if dependency.target_file else None,
            "imported_module": dependency.imported_module,
        }
        for dependency, source_path in dependencies
    ]
@router.get("/{repo_id}/files", response_model=PaginatedFiles)
def get_repository_files(
    repo_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(File).filter(File.repository_id == repo_id)
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return {"items": items, "total": total, "page": page, "size": size}
@router.get("/{repo_id}/symbols", response_model=PaginatedSymbols)
def get_repository_symbols(
    repo_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    # Join File to filter by repo_id
    query = db.query(Symbol).join(File).filter(File.repository_id == repo_id)
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return {"items": items, "total": total, "page": page, "size": size}
@router.get("/{repo_id}/commits", response_model=PaginatedCommits)
def get_repository_commits(
    repo_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    query = db.query(Commit).filter(Commit.repository_id == repo_id).order_by(Commit.committed_at.desc())
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return {"items": items, "total": total, "page": page, "limit": limit}
@router.get("/{repo_id}/commits/{sha}/changes", response_model=List[CommitChangeResponse])
def get_commit_changes(
    repo_id: int,
    sha: str,
    db: Session = Depends(get_db)
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    commit = db.query(Commit).filter(Commit.repository_id == repo_id, Commit.sha == sha).first()
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found in this repository")
    changes = db.query(CommitFileChange).filter(CommitFileChange.commit_id == commit.id).all()
    return changes

@router.get("/{repo_id}/files/{file_id}/commits", response_model=PaginatedFileCommits)
def get_file_commits(
    repo_id: int,
    file_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    file = db.query(File).filter(File.id == file_id, File.repository_id == repo_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found in this repository")

    # Query commits that changed this file
    query = (
        db.query(Commit)
        .join(CommitFileChange)
        .filter(CommitFileChange.file_id == file_id)
        .order_by(Commit.committed_at.desc())
    )

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()

    return {"items": items, "total": total, "page": page, "limit": limit}
@router.get("/{repo_id}/files/{file_id}/churn", response_model=FileChurnResponse)
def get_file_churn(
    repo_id: int,
    file_id: int,
    db: Session = Depends(get_db)
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    file = db.query(File).filter(File.id == file_id, File.repository_id == repo_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found in this repository")

    changes = (
        db.query(CommitFileChange)
        .join(Commit, CommitFileChange.commit_id == Commit.id)
        .filter(
            Commit.repository_id == repo_id,
            CommitFileChange.file_id == file_id,
        )
        .all()
    )

    counts = {"added": 0, "modified": 0, "deleted": 0, "renamed": 0}
    for change in changes:
        if change.change_type in counts:
            counts[change.change_type] += 1

    return {
        "file_id": file.id,
        "path": file.path,
        "total_changes": len(changes),
        "added_count": counts["added"],
        "modified_count": counts["modified"],
        "deleted_count": counts["deleted"],
        "renamed_count": counts["renamed"],
    }

@router.get("/{repo_id}/hotspots", response_model=List[FileHotspotResponse])
def get_repository_hotspots(
    repo_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    recent_cutoff = datetime.utcnow() - timedelta(days=HOTSPOT_RECENT_WINDOW_DAYS)

    rows = (
        db.query(
            File.id.label("file_id"),
            File.path.label("path"),
            func.count(CommitFileChange.id).label("total_changes"),
            func.sum(
                case((Commit.committed_at >= recent_cutoff, 1), else_=0)
            ).label("recent_changes"),
            func.max(Commit.committed_at).label("last_changed_at"),
        )
        .join(CommitFileChange, CommitFileChange.file_id == File.id)
        .join(Commit, CommitFileChange.commit_id == Commit.id)
        .filter(
            File.repository_id == repo_id,
            Commit.repository_id == repo_id,
            CommitFileChange.file_id.isnot(None),
        )
        .group_by(File.id, File.path)
        .order_by(
            func.count(CommitFileChange.id).desc(),
            func.max(Commit.committed_at).desc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "file_id": row.file_id,
            "path": row.path,
            "total_changes": row.total_changes,
            "recent_changes": row.recent_changes,
            "last_changed_at": row.last_changed_at,
        }
        for row in rows
    ]

@router.get("/{repo_id}/chunks", response_model=PaginatedChunks)
def get_repository_chunks(
    repo_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    chunk_type: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    query = db.query(Chunk).filter(Chunk.repository_id == repo_id)
    if chunk_type is not None:
        query = query.filter(Chunk.chunk_type == chunk_type)

    # Deterministic ordering so paging is stable across requests.
    query = query.order_by(Chunk.path, Chunk.start_line, Chunk.id)

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return {"items": items, "total": total, "page": page, "limit": limit}

@router.get("/{repo_id}/embeddings", response_model=EmbeddingStatusResponse)
def get_repository_embedding_status(repo_id: int, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    total = db.query(Chunk).filter(Chunk.repository_id == repo_id).count()
    pending = count_pending_chunks(db, repo_id)
    return {
        "repository_id": repo_id,
        "total_chunks": total,
        "embedded_chunks": total - pending,
        "pending_chunks": pending,
        "model": get_model_name(),
        "dimension": get_dimension(),
    }

@router.post("/{repo_id}/embeddings", response_model=EmbeddingResultResponse)
def create_repository_embeddings(
    repo_id: int,
    force: bool = Query(False),
    db: Session = Depends(get_db)
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        return embed_repository_chunks(db, repo_id, force=force)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding provider unavailable: {exc}")

@router.get("/{repo_id}/search", response_model=SearchResponse)
def search_repository(
    repo_id: int,
    q: str = Query(..., min_length=1),
    mode: str = Query("hybrid", pattern="^(semantic|lexical|hybrid)$"),
    limit: int = Query(10, ge=1, le=50),
    chunk_type: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    path: Optional[str] = Query(None),
    symbol_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be blank")

    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from services.search.hybrid_search import perform_search

    results, total = perform_search(
        db, repo_id, q, mode, limit,
        chunk_type, language, path, symbol_name
    )

    return {
        "query": q,
        "results": results,
        "total": total
    }

@router.get("/{repo_id}/context", response_model=ContextAssemblyResponse)
def assemble_repository_context(
    repo_id: int,
    q: str = Query(..., min_length=1),
    mode: str = Query("hybrid", pattern="^(semantic|lexical|hybrid)$"),
    limit: int = Query(50, ge=1, le=100),
    budget: Optional[int] = Query(None, ge=1),
    chunk_type: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    path: Optional[str] = Query(None),
    symbol_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be blank")

    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from services.context.assembler import assemble_context

    # We reuse the hybrid search engine under the hood
    context_data = assemble_context(
        db, repo_id, q, mode, limit, budget,
        chunk_type, language, path, symbol_name
    )

    return context_data
