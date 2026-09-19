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
extract_commits = _git_svc.extract_commits
discover_files = _git_svc.discover_files
detect_language = _parser_svc.detect_language
parse_file = _parser_svc.parse_file
extract_imports = _parser_svc.extract_imports

from database import SessionLocal
from models import (
    Repository,
    File as DBFile,
    Symbol as DBSymbol,
    Dependency as DBDependency,
    Commit as DBCommit,
    RepositoryStatus,
)

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

        existing_commits = {
            commit.sha
            for commit in db.query(DBCommit).filter(DBCommit.repository_id == repo.id).all()
        }
        for commit in extract_commits(temp_dir):
            if commit["sha"] in existing_commits:
                continue
            db.add(DBCommit(repository_id=repo.id, **commit))
        db.commit()
        
        repo.status = RepositoryStatus.parsing
        db.commit()
        
        # Discover files
        files = discover_files(temp_dir)
        
        db_files = {}
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
            db_files[file_rel_path.replace(os.sep, '/')] = db_file
            
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

        for file_rel_path, db_file in db_files.items():
            file_abs_path = os.path.join(temp_dir, file_rel_path)
            try:
                imports = extract_imports(file_abs_path)
                for imported_module in imports:
                    target_path = _resolve_import(file_rel_path, imported_module, db_files)
                    db.add(DBDependency(
                        source_file_id=db_file.id,
                        target_file_id=db_files[target_path].id if target_path else None,
                        imported_module=imported_module,
                    ))
            except Exception:
                pass
        db.commit()
                    
        repo.status = RepositoryStatus.completed
        db.commit()
        
    except Exception as e:
        print(f"INGESTION ERROR: {type(e).__name__}: {e}")
        repo.status = RepositoryStatus.failed
        db.commit()
    finally:
        db.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


def _resolve_import(source_path, imported_module, db_files):
    """Resolve a local Python or JavaScript import to a discovered file."""
    source_dir = os.path.dirname(source_path)
    if imported_module.startswith('.'):
        relative = imported_module
        while relative.startswith('.'):
            source_dir = os.path.dirname(source_dir)
            relative = relative[1:]
        base = os.path.join(source_dir, relative.replace('.', os.sep))
    else:
        base = imported_module.replace('.', os.sep)
        if source_path.endswith(('.js', '.jsx', '.ts', '.tsx')) and not imported_module.startswith('@'):
            base = os.path.join(source_dir, imported_module)

    base = base.replace(os.sep, '/')
    candidates = [base]
    if not os.path.splitext(base)[1]:
        candidates.extend([
            f'{base}.py', f'{base}.js', f'{base}.jsx', f'{base}.ts', f'{base}.tsx',
            f'{base}/__init__.py', f'{base}/index.js', f'{base}/index.ts',
        ])

    return next((candidate for candidate in candidates if candidate in db_files), None)
