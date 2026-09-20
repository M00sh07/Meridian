from typing import List, Optional
from sqlalchemy.orm import Session
from services.search.hybrid_search import perform_search

def assemble_context(
    db: Session,
    repo_id: int,
    query: str,
    mode: str,
    limit: int,
    budget: Optional[int] = None,
    chunk_type: Optional[str] = None,
    language: Optional[str] = None,
    path: Optional[str] = None,
    symbol_name: Optional[str] = None
) -> dict:

    # 1. Fetch from underlying hybrid engine
    results, _ = perform_search(
        db, repo_id, query, mode, limit,
        chunk_type, language, path, symbol_name
    )

    seen_chunk_ids = set()
    grouped_files = {} # path -> list of chunks
    current_size = 0

    for res in results:
        cid = res["chunk_id"]
        if cid in seen_chunk_ids:
            continue

        content_len = len(res["content"])

        # Enforce budget limit deterministically if provided
        if budget is not None and (current_size + content_len) > budget:
            continue

        seen_chunk_ids.add(cid)
        c_path = res["path"] or "unknown_path"

        if c_path not in grouped_files:
            grouped_files[c_path] = []

        grouped_files[c_path].append(res)
        current_size += content_len

    # Group results deterministically by file, sorted by max score within file
    file_groups = []
    for fpath, chunks in grouped_files.items():
        # Within a file, chunks should be ordered logically by line number to present as coherent text
        chunks.sort(key=lambda x: x["start_line"] or 0)

        max_score = max(c["score"] for c in chunks)
        file_groups.append({
            "path": fpath,
            "chunks": chunks,
            "max_score": max_score
        })

    # Files with the highest scoring chunks appear first
    file_groups.sort(key=lambda x: (-x["max_score"], x["path"]))

    final_files = []
    for fg in file_groups:
        parsed_chunks = []
        for c in fg["chunks"]:
            parsed_chunks.append({
                "chunk_id": c["chunk_id"],
                "chunk_type": c["chunk_type"],
                "symbol_name": c["symbol_name"],
                "language": c["language"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "content": c["content"],
                "score": c["score"],
                "semantic_score": c["semantic_score"],
                "lexical_score": c["lexical_score"]
            })

        final_files.append({
            "path": fg["path"],
            "chunks": parsed_chunks
        })

    return {
        "query": query,
        "repository_id": repo_id,
        "files": final_files,
        "total_chunks": len(seen_chunk_ids),
        "total_characters": current_size
    }
