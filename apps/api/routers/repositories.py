import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from database import get_db
from models import Repository, File, Symbol, Dependency, RepositoryStatus, Commit, CommitFileChange
from schemas import (
    RepositoryCreate,
    RepositoryResponse,
    DependencyResponse,
    PaginatedFiles,
    PaginatedSymbols,
    PaginatedCommits,
    CommitChangeResponse,
    PaginatedFileCommits,
)
from services.ingestion_job import process_repository
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
