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
