"""Batch embedding of stored chunks.

Idempotency rule: a chunk is re-embedded only when its `content_hash` differs
from `embedded_content_hash`. Chunks already embedded at the current hash are
skipped, so repeated runs are cheap and produce no writes.

Failure safety: chunks are embedded in batches and each batch is committed
independently. If the provider raises, the affected chunks are left untouched
(their previous embedding and all chunk data are preserved) and the failure is
reported back to the caller rather than propagated as corruption.
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models import Chunk
from services.embedding_provider import get_provider

DEFAULT_BATCH_SIZE = 16


def _current_provider():
    return get_provider()


def embed_repository_chunks(db: Session, repo_id: int, batch_size: int = DEFAULT_BATCH_SIZE,
                            provider=None, force: bool = False) -> Dict:
    """Embed chunks for one repository.

    Returns a summary dict with counts of embedded / skipped / failed chunks.
    """
    provider = provider or _current_provider()
    model_name = provider.model_name
    dimension = provider.dimension

    chunks = (
        db.query(Chunk)
        .filter(Chunk.repository_id == repo_id)
        .order_by(Chunk.id)
        .all()
    )

    pending = [
        chunk for chunk in chunks
        if force or chunk.embedded_content_hash != chunk.content_hash or chunk.embedding is None
    ]
    skipped = len(chunks) - len(pending)

    embedded = 0
    failed = 0
    errors: List[str] = []

    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]
        texts = [chunk.content for chunk in batch]
        try:
            vectors = provider.embed(texts)
        except Exception as exc:  # provider failure must not corrupt chunk data
            failed += len(batch)
            errors.append(f"{type(exc).__name__}: {exc}")
            continue

        if len(vectors) != len(batch):
            failed += len(batch)
            errors.append(
                f"provider returned {len(vectors)} vectors for {len(batch)} chunks"
            )
            continue

        now = datetime.utcnow()
        for chunk, vector in zip(batch, vectors):
            # Assign only after every vector in the batch is in hand, so a
            # partial failure never leaves a half-updated batch persisted.
            chunk.embedding = list(vector)
            chunk.embedding_model = model_name
            chunk.embedding_dimension = dimension
            chunk.embedded_content_hash = chunk.content_hash
            chunk.embedded_at = now
        db.commit()
        embedded += len(batch)

    return {
        "repository_id": repo_id,
        "total_chunks": len(chunks),
        "embedded": embedded,
        "skipped": skipped,
        "failed": failed,
        "model": model_name,
        "dimension": dimension,
        "errors": errors,
    }


def count_pending_chunks(db: Session, repo_id: int, force: bool = False) -> int:
    """Count chunks that would be embedded, without calling the provider."""
    query = db.query(Chunk).filter(Chunk.repository_id == repo_id)
    if force:
        return query.count()
    return query.filter(
        (Chunk.embedded_content_hash != Chunk.content_hash) | (Chunk.embedding.is_(None))
    ).count()
