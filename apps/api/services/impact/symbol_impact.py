from sqlalchemy.orm import Session
from fastapi import HTTPException
from models import File, Symbol, Repository
from services.impact.dependency_impact import get_dependency_impact
from schemas import SymbolImpactResponse, SymbolImpactTarget

def get_symbol_impact(db: Session, repo_id: int, path: str, symbol_name: str, depth: int = 1) -> SymbolImpactResponse:
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

    target_symbol = db.query(Symbol).filter(
        Symbol.file_id == target_file.id,
        Symbol.name == symbol_name
    ).first()

    if not target_symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")

    # Reuse file-level impact
    # Use target_file.path directly since we confirmed it matches in the DB
    file_impact = get_dependency_impact(db, repo_id, target_file.path, depth)

    target_info = SymbolImpactTarget(
        file_id=target_file.id,
        path=target_file.path,
        symbol_id=target_symbol.id,
        symbol_name=target_symbol.name,
        symbol_type=target_symbol.type,
        start_line=target_symbol.start_line,
        end_line=target_symbol.end_line
    )

    return SymbolImpactResponse(
        repository_id=repo_id,
        target_symbol=target_info,
        depth=depth,
        file_level_direct_dependencies=file_impact.get("direct_dependencies", []),
        file_level_direct_dependents=file_impact.get("direct_dependents", []),
        file_level_affected_files=file_impact.get("affected_files", []),
        file_level_total_affected=file_impact.get("total_affected", 0)
    )

