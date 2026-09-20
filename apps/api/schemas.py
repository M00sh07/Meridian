from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from models import RepositoryStatus

class RepositoryCreate(BaseModel):
    url: str

class RepositoryResponse(BaseModel):
    id: int
    url: str
    status: RepositoryStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class FileResponse(BaseModel):
    id: int
    repository_id: int
    path: str
    language: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class SymbolResponse(BaseModel):
    id: int
    file_id: int
    name: str
    type: str
    signature: Optional[str] = None
    start_line: int
    end_line: int

    model_config = ConfigDict(from_attributes=True)

class DependencyResponse(BaseModel):
    source_file: str
    target_file: Optional[str] = None
    imported_module: str

class PaginatedFiles(BaseModel):
    items: List[FileResponse]
    total: int
    page: int
    size: int

class PaginatedSymbols(BaseModel):
    items: List[SymbolResponse]
    total: int
    page: int
    size: int


class CommitChangeResponse(BaseModel):
    path: str
    previous_path: Optional[str] = None
    change_type: str
    file_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class CommitResponse(BaseModel):
    sha: str
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    message: str
    committed_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PaginatedCommits(BaseModel):
    items: List[CommitResponse]
    total: int
    page: int
    limit: int

class PaginatedFileCommits(BaseModel):
    items: List[CommitResponse]
    total: int
    page: int
    limit: int
class FileChurnResponse(BaseModel):
    file_id: int
    path: str
    total_changes: int
    added_count: int
    modified_count: int
    deleted_count: int
    renamed_count: int
class FileHotspotResponse(BaseModel):
    file_id: int
    path: str
    total_changes: int
    recent_changes: int
    last_changed_at: Optional[datetime] = None
class ChunkResponse(BaseModel):
    id: int
    repository_id: int
    file_id: Optional[int] = None
    symbol_id: Optional[int] = None
    chunk_type: str
    path: str
    symbol_name: Optional[str] = None
    symbol_type: Optional[str] = None
    language: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    content: str
    content_hash: str
    model_config = ConfigDict(from_attributes=True)

class PaginatedChunks(BaseModel):
    items: List[ChunkResponse]
    total: int
    page: int
    limit: int
class EmbeddingStatusResponse(BaseModel):
    repository_id: int
    total_chunks: int
    embedded_chunks: int
    pending_chunks: int
    model: str
    dimension: int
class EmbeddingResultResponse(BaseModel):
    repository_id: int
    total_chunks: int
    embedded: int
    skipped: int
    failed: int
    model: str
    dimension: int
    errors: List[str]

class SearchResultResponse(BaseModel):
    chunk_id: int
    path: str
    chunk_type: str
    symbol_name: Optional[str] = None
    language: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    content: str
    similarity: float
    score: Optional[float] = None
    semantic_score: Optional[float] = None
    lexical_score: Optional[float] = None

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultResponse]
    total: int

class ContextChunkResponse(BaseModel):
    chunk_id: int
    chunk_type: str
    symbol_name: Optional[str] = None
    language: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    content: str
    score: float
    semantic_score: float
    lexical_score: float

class ContextFileGroupResponse(BaseModel):
    path: str
    chunks: List[ContextChunkResponse]

class ContextAssemblyResponse(BaseModel):
    query: str
    repository_id: int
    files: List[ContextFileGroupResponse]
    total_chunks: int
    total_characters: int

class ImpactTarget(BaseModel):
    file_id: int
    path: str

class ImpactNode(BaseModel):
    file_id: int
    path: str
    relationship: str
    depth: int

class DependencyImpactResponse(BaseModel):
    repository_id: int
    target: ImpactTarget
    depth: int
    direct_dependencies: List[ImpactNode]
    direct_dependents: List[ImpactNode]
    affected_files: List[ImpactNode]
    total_affected: int

class HistoryCommit(BaseModel):
    sha: str
    author_name: Optional[str] = None
    message: str
    committed_at: datetime
    change_type: str
    previous_path: Optional[str] = None

class CoChangeNode(BaseModel):
    file_id: int
    path: str
    shared_commits: int

class HistoricalImpactResponse(BaseModel):
    repository_id: int
    target: ImpactTarget
    total_changes: int
    first_commit_date: Optional[datetime] = None
    last_commit_date: Optional[datetime] = None
    recent_commits: List[HistoryCommit]
    co_changes: List[CoChangeNode]

class SymbolImpactTarget(BaseModel):
    file_id: int
    path: str
    symbol_id: int
    symbol_name: str
    symbol_type: str
    start_line: int
    end_line: int

class SymbolImpactResponse(BaseModel):
    repository_id: int
    target_symbol: SymbolImpactTarget
    depth: int
    file_level_direct_dependencies: List[ImpactNode]
    file_level_direct_dependents: List[ImpactNode]
    file_level_affected_files: List[ImpactNode]
    file_level_total_affected: int
