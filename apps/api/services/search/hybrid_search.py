import os
import math
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from models import Chunk
from services.search.lexical_search import get_lexical_candidates, score_lexical
from services.search.tokenizer import tokenize
from services.embedding_provider import get_provider
from fastapi import HTTPException

def get_hybrid_config() -> Tuple[float, float, int]:
    try:
        sw = float(os.getenv("SEMANTIC_SEARCH_WEIGHT", "0.70"))
    except ValueError:
        sw = 0.70
    try:
        lw = float(os.getenv("LEXICAL_SEARCH_WEIGHT", "0.30"))
    except ValueError:
        lw = 0.30

    try:
        cm = int(os.getenv("HYBRID_CANDIDATE_MULTIPLIER", "5"))
    except ValueError:
        cm = 5

    if sw < 0 or lw < 0 or (sw + lw) <= 0:
        sw, lw = 0.70, 0.30

    # Normalize weights so they sum to 1.0
    total = sw + lw
    return sw / total, lw / total, max(1, cm)

def get_semantic_candidates(
    db: Session,
    repo_id: int,
    query_vector: List[float],
    limit: int,
    chunk_type: Optional[str] = None,
    language: Optional[str] = None,
    path: Optional[str] = None,
    symbol_name: Optional[str] = None
) -> Tuple[List[Tuple[Chunk, float]], int]:
    """Returns (candidates_with_scores, total_matching_chunks)"""
    base_query = db.query(Chunk).filter(
        Chunk.repository_id == repo_id,
        Chunk.embedding.isnot(None)
    )

    if chunk_type:
        base_query = base_query.filter(Chunk.chunk_type == chunk_type)
    if language:
        base_query = base_query.filter(Chunk.language == language)
    if path:
        base_query = base_query.filter(Chunk.path == path)
    if symbol_name:
        base_query = base_query.filter(Chunk.symbol_name == symbol_name)

    total_count = base_query.count()
    dialect = db.get_bind().dialect.name
    results = []

    if dialect == "postgresql":
        distance = Chunk.embedding.op('<=>')(list(query_vector))
        db_results = base_query.add_columns(
            (1.0 - distance).label('similarity')
        ).order_by(distance).limit(limit).all()
        for chunk, sim in db_results:
            results.append((chunk, float(sim)))
    else:
        all_chunks = base_query.all()
        scored_chunks = []

        def cosine_sim(v1, v2):
            dot = sum(a * b for a, b in zip(v1, v2))
            norm1 = math.sqrt(sum(a * a for a in v1))
            norm2 = math.sqrt(sum(b * b for b in v2))
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot / (norm1 * norm2)

        for chunk in all_chunks:
            if not chunk.embedding:
                continue
            sim = cosine_sim(list(query_vector), chunk.embedding)
            scored_chunks.append((sim, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        for sim, chunk in scored_chunks[:limit]:
            results.append((chunk, float(sim)))

    return results, total_count

def perform_search(
    db: Session,
    repo_id: int,
    q: str,
    mode: str,
    limit: int,
    chunk_type: Optional[str] = None,
    language: Optional[str] = None,
    path: Optional[str] = None,
    symbol_name: Optional[str] = None
) -> Tuple[List[dict], int]:

    sw, lw, cm = get_hybrid_config()
    candidate_limit = limit * cm

    query_tokens = tokenize(q)

    semantic_candidates = {}
    lexical_candidates = {}
    total = 0

    if mode in ("semantic", "hybrid"):
        provider = get_provider()
        try:
            query_vector = provider.embed([q])[0]
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Embedding provider unavailable: {exc}")

        sem_results, sem_total = get_semantic_candidates(
            db, repo_id, query_vector, candidate_limit,
            chunk_type, language, path, symbol_name
        )
        for chunk, sim in sem_results:
            semantic_candidates[chunk.id] = (chunk, sim)
        total = sem_total # total matching metadata

    if mode in ("lexical", "hybrid"):
        lex_chunks = get_lexical_candidates(
            db, repo_id, q, candidate_limit,
            chunk_type, language, path, symbol_name
        )

        for chunk in lex_chunks:
            l_score = score_lexical(q, query_tokens, chunk)
            lexical_candidates[chunk.id] = (chunk, l_score)

        # For lexical and hybrid modes, total is all chunks matching metadata filters
        if mode in ("lexical", "hybrid"):
            base_query = db.query(Chunk).filter(Chunk.repository_id == repo_id)
            if chunk_type:
                base_query = base_query.filter(Chunk.chunk_type == chunk_type)
            if language:
                base_query = base_query.filter(Chunk.language == language)
            if path:
                base_query = base_query.filter(Chunk.path == path)
            if symbol_name:
                base_query = base_query.filter(Chunk.symbol_name == symbol_name)
            total = base_query.count()

    # Union candidates
    all_chunk_ids = set(semantic_candidates.keys()) | set(lexical_candidates.keys())

    scored_results = []
    for cid in all_chunk_ids:
        chunk = None
        s_score = 0.0
        l_score = 0.0

        if cid in semantic_candidates:
            chunk, s_score = semantic_candidates[cid]
        if cid in lexical_candidates:
            chunk, l_score = lexical_candidates[cid]
            if chunk is None:
                chunk = lexical_candidates[cid][0]

        # If chunk is fetched only by semantic, calculate lexical anyway for accurate hybrid score
        if mode == "hybrid" and cid not in lexical_candidates:
            l_score = score_lexical(q, query_tokens, chunk)

        # If fetched only by lexical, semantic score remains 0 (or whatever it is if missing embedding)

        if mode == "semantic":
            final_score = s_score
        elif mode == "lexical":
            final_score = l_score
        else:
            final_score = (sw * s_score) + (lw * l_score)

        scored_results.append({
            "chunk": chunk,
            "final_score": final_score,
            "semantic_score": s_score,
            "lexical_score": l_score
        })

    # Sort deterministically
    # 1. final_score desc, 2. semantic_score desc, 3. lexical_score desc, 4. path asc, 5. start_line asc, 6. chunk_id asc
    scored_results.sort(key=lambda x: (
        -x["final_score"],
        -x["semantic_score"],
        -x["lexical_score"],
        x["chunk"].path or "",
        x["chunk"].start_line or 0,
        x["chunk"].id
    ))

    final_results = []
    for sr in scored_results[:limit]:
        c = sr["chunk"]
        final_results.append({
            "chunk_id": c.id,
            "path": c.path,
            "chunk_type": c.chunk_type,
            "symbol_name": c.symbol_name,
            "language": c.language,
            "start_line": c.start_line,
            "end_line": c.end_line,
            "content": c.content,
            "similarity": sr["final_score"], # legacy field
            "score": sr["final_score"],
            "semantic_score": sr["semantic_score"],
            "lexical_score": sr["lexical_score"]
        })

    return final_results, total
