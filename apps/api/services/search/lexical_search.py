from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import case, desc, func
from models import Chunk
from services.search.tokenizer import tokenize

def get_lexical_candidates(
    db: Session,
    repo_id: int,
    query: str,
    limit: int,
    chunk_type: Optional[str] = None,
    language: Optional[str] = None,
    path: Optional[str] = None,
    symbol_name: Optional[str] = None
) -> List[Chunk]:
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    base_query = db.query(Chunk).filter(Chunk.repository_id == repo_id)

    if chunk_type:
        base_query = base_query.filter(Chunk.chunk_type == chunk_type)
    if language:
        base_query = base_query.filter(Chunk.language == language)
    if path:
        base_query = base_query.filter(Chunk.path == path)
    if symbol_name:
        base_query = base_query.filter(Chunk.symbol_name == symbol_name)

    # Prioritize exact matches in symbol/path over content matches
    conditions = []
    query_lower = query.lower()
    if query_lower:
        conditions.append((func.lower(Chunk.symbol_name) == query_lower, 3))
        conditions.append((func.lower(Chunk.path) == query_lower, 3))

    for t in query_tokens:
        t_lower = t.lower()
        conditions.append((Chunk.symbol_name.ilike(f"%{t_lower}%"), 2))
        conditions.append((Chunk.path.ilike(f"%{t_lower}%"), 2))

    for t in query_tokens:
        t_lower = t.lower()
        conditions.append((Chunk.content.ilike(f"%{t_lower}%"), 1))

    case_stmt = case(*conditions, else_=0)

    base_query = base_query.filter(case_stmt > 0)
    return base_query.order_by(desc(case_stmt), Chunk.id).limit(limit).all()

def score_lexical(query: str, query_tokens: List[str], chunk: Chunk) -> float:
    """
    Scores a chunk based on lexical overlap with the query.
    Returns a score between 0.0 and 1.0.
    """
    if not query_tokens:
        return 0.0

    score = 0.0
    query_lower = query.lower()

    c_symbol_raw = chunk.symbol_name or ""
    c_path_raw = chunk.path or ""
    c_content_raw = chunk.content or ""

    c_symbol_lower = c_symbol_raw.lower()
    c_path_lower = c_path_raw.lower()
    c_content_lower = c_content_raw.lower()

    # 1. Highest signal: Exact symbol_name, path, or identifier match
    if c_symbol_lower and query_lower == c_symbol_lower:
        return 1.0
    if c_path_lower and query_lower == c_path_lower:
        return 1.0

    if query_lower in c_content_lower:
        score += 0.5 # Exact identifier match in content is very strong

    # 2. Token-level signals (DO NOT lowercase before tokenize)
    c_symbol_tokens = set(tokenize(c_symbol_raw))
    c_path_tokens = set(tokenize(c_path_raw))

    symbol_overlap = sum(1 for t in query_tokens if t in c_symbol_tokens)
    path_overlap = sum(1 for t in query_tokens if t in c_path_tokens)

    # Strong signal: tokens present in symbol or path
    if symbol_overlap > 0:
        score += 0.3 * (symbol_overlap / len(query_tokens))
    if path_overlap > 0:
        score += 0.2 * (path_overlap / len(query_tokens))

    # Moderate signal: tokens in content
    content_overlap = sum(1 for t in query_tokens if t in c_content_lower)
    if content_overlap > 0:
        score += 0.2 * (content_overlap / len(query_tokens))

    return min(1.0, score)
