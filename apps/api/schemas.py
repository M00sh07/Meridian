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
