import os
import shutil
import tempfile
import sys
import importlib.util
from sqlalchemy.orm import Session

_MONOREPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

def _load_module(dotted_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(
        dotted_name,
        os.path.join(_MONOREPO_ROOT, rel_path)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_git_svc = _load_module("git_service", "services/ingestion/git_service.py")
_parser_svc = _load_module("tree_sitter_service", "services/parser/tree_sitter_service.py")
clone_repository = _git_svc.clone_repository
discover_files = _git_svc.discover_files
detect_language = _parser_svc.detect_language
parse_file = _parser_svc.parse_file

from database import SessionLocal
from models import Repository, File as DBFile, Symbol as DBSymbol, RepositoryStatus

def process_repository(repo_id: int):
    db: Session = SessionLocal()
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        db.close()
        return

    temp_dir = tempfile.mkdtemp()
    
    try:
        repo.status = RepositoryStatus.cloning
        db.commit()
        
        # Clone repo
        clone_repository(repo.url, temp_dir)
        
        repo.status = RepositoryStatus.parsing
        db.commit()
        
        # Discover files
        files = discover_files(temp_dir)
        
        for file_rel_path in files:
            file_abs_path = os.path.join(temp_dir, file_rel_path)
            lang = detect_language(file_abs_path)
            
            db_file = DBFile(
                repository_id=repo.id,
                path=file_rel_path,
                language=lang
            )
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
            
            if lang:
                try:
                    symbols = parse_file(file_abs_path)
                    for sym in symbols:
                        db_sym = DBSymbol(
                            file_id=db_file.id,
                            name=sym['name'],
                            type=sym['type'],
                            signature=sym['signature'],
                            start_line=sym['start_line'],
                            end_line=sym['end_line']
                        )
                        db.add(db_sym)
                    db.commit()
                except Exception as e:
                    # Log parsing error but continue
                    pass
                    
        repo.status = RepositoryStatus.completed
        db.commit()
        
    except Exception as e:
        repo.status = RepositoryStatus.failed
        db.commit()
    finally:
        db.close()
        shutil.rmtree(temp_dir, ignore_errors=True)
