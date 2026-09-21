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
_chunking_svc = _load_module("chunking_service", "services/parser/chunking_service.py")
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
    CommitFileChange as DBCommitFileChange,
    Chunk as DBChunk,
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
        # Store changes for later
        commit_changes_map = {}

        # Use updated git service method
        for commit_data in _git_svc.extract_commits_with_changes(temp_dir):
            if commit_data["sha"] in existing_commits:
                continue

            changes = commit_data.pop("changes")
            commit_obj = DBCommit(repository_id=repo.id, **commit_data)
            db.add(commit_obj)
            db.flush() # Get ID

            commit_changes_map[commit_obj.sha] = (commit_obj.id, changes)

        db.commit()

        repo.status = RepositoryStatus.parsing
        db.commit()

        # Discover files
        files = discover_files(temp_dir)

        # Reuse File rows already stored for this repository so that re-ingesting
        # the same repository does not duplicate files, symbols or dependencies.
        existing_files = {
            file.path: file
            for file in db.query(DBFile).filter(DBFile.repository_id == repo.id).all()
        }

        # Map path -> (DBFile, absolute path, symbol rows) so chunking can reuse
        # both newly parsed and previously stored files without re-inserting them.
        db_files = {}
        file_symbols = {}

        for file_rel_path in files:
            file_abs_path = os.path.join(temp_dir, file_rel_path)
            normalized_path = file_rel_path.replace(os.sep, '/')

            existing_file = existing_files.get(normalized_path)
            if existing_file:
                # Already ingested; reuse the row and its persisted symbols.
                db_files[normalized_path] = existing_file
                file_symbols[normalized_path] = [
                    {
                        'id': symbol.id,
                        'name': symbol.name,
                        'type': symbol.type,
                        'start_line': symbol.start_line,
                        'end_line': symbol.end_line,
                    }
                    for symbol in db.query(DBSymbol)
                    .filter(DBSymbol.file_id == existing_file.id)
                    .order_by(DBSymbol.start_line, DBSymbol.id)
                    .all()
                ]
                continue
            lang = detect_language(file_abs_path)

            db_file = DBFile(
                repository_id=repo.id,
                path=normalized_path,
                language=lang
            )
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
            db_files[normalized_path] = db_file
            stored_symbols = []
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
                        db.flush()
                        stored_symbols.append({
                            'id': db_sym.id,
                            'name': db_sym.name,
                            'type': db_sym.type,
                            'start_line': db_sym.start_line,
                            'end_line': db_sym.end_line,
                        })
                    db.commit()
                except Exception as e:
                    # Log parsing error but continue
                    pass
            file_symbols[normalized_path] = stored_symbols

        existing_deps = {
            (dep.source_file_id, dep.imported_module): dep
            for dep in db.query(DBDependency).join(
                DBFile, DBDependency.source_file_id == DBFile.id
            ).filter(DBFile.repository_id == repo.id).all()
        }
        seen_deps = set()

        for file_rel_path, db_file in db_files.items():
            file_abs_path = os.path.join(temp_dir, file_rel_path.replace('/', os.sep))
            try:
                imports = extract_imports(file_abs_path)
                for imported_module in imports:
                    target_path = _resolve_import(file_rel_path, imported_module, db_files)
                    target_id = db_files[target_path].id if target_path else None
                    
                    key = (db_file.id, imported_module)
                    seen_deps.add(key)
                    
                    if key in existing_deps:
                        existing_deps[key].target_file_id = target_id
                    else:
                        new_dep = DBDependency(
                            source_file_id=db_file.id,
                            target_file_id=target_id,
                            imported_module=imported_module,
                        )
                        db.add(new_dep)
                        existing_deps[key] = new_dep
            except Exception as e:
                print(f"Dependency extraction failed for {file_rel_path}: {e}")
                # Preserve existing dependencies so they are not swept away
                for key in existing_deps:
                    if key[0] == db_file.id:
                        seen_deps.add(key)
                
        for key, dep in list(existing_deps.items()):
            if key not in seen_deps:
                db.delete(dep)
                
        db.commit()

        # Build deterministic semantic chunks. Re-ingestion updates existing
        # chunks in place (matched by chunk_key) instead of duplicating them.
        _store_chunks(db, repo.id, db_files, file_symbols, temp_dir)

        # Add commit file changes
        for sha, (commit_id, changes) in commit_changes_map.items():
            for change in changes:
                file_path = change["path"].replace(os.sep, '/')
                # Try to find corresponding DBFile
                db_file = db_files.get(file_path)

                db.add(DBCommitFileChange(
                    commit_id=commit_id,
                    file_id=db_file.id if db_file else None,
                    path=file_path,
                    previous_path=change.get("previous_path"),
                    change_type=change["type"]
                ))
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


def _store_chunks(db, repo_id, db_files, file_symbols, temp_dir):
    # Create or refresh semantic chunks for every discovered file. Chunks are
    # matched on (repository_id, chunk_key) so re-ingestion updates the existing
    # row rather than inserting a duplicate.
    existing_chunks = {
        chunk.chunk_key: chunk
        for chunk in db.query(DBChunk).filter(DBChunk.repository_id == repo_id).all()
    }

    for path, db_file in db_files.items():
        file_abs_path = os.path.join(temp_dir, path.replace('/', os.sep))
        built = _chunking_svc.build_file_chunks(
            path=path,
            file_path=file_abs_path,
            language=db_file.language,
            symbols=file_symbols.get(path, []),
        )

        seen_keys = set()
        for chunk_data in built:
            chunk_key = chunk_data['chunk_key']
            seen_keys.add(chunk_key)
            existing = existing_chunks.get(chunk_key)

            if existing:
                existing.file_id = db_file.id
                existing.symbol_id = chunk_data['symbol_id']
                existing.chunk_type = chunk_data['chunk_type']
                existing.path = chunk_data['path']
                existing.symbol_name = chunk_data['symbol_name']
                existing.symbol_type = chunk_data['symbol_type']
                existing.language = chunk_data['language']
                existing.start_line = chunk_data['start_line']
                existing.end_line = chunk_data['end_line']
                existing.content = chunk_data['content']
                existing.content_hash = chunk_data['content_hash']
            else:
                db.add(DBChunk(
                    repository_id=repo_id,
                    file_id=db_file.id,
                    **chunk_data,
                ))

        # Drop chunks for this file that no longer correspond to any content
        # (e.g. a symbol was removed).
        for chunk_key, stale in list(existing_chunks.items()):
            if stale.path == path and chunk_key not in seen_keys:
                db.delete(stale)
                del existing_chunks[chunk_key]

    db.commit()


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
