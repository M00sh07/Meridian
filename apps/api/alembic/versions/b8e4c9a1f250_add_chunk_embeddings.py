"""add_chunk_embeddings

Revision ID: b8e4c9a1f250
Revises: a7f3b2c81d40
Create Date: 2026-09-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import os
import sys

# apps/api must be importable so the configured embedding dimension is reused.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.embedding_config import get_dimension


# revision identifiers, used by Alembic.
revision: str = 'b8e4c9a1f250'
down_revision: Union[str, Sequence[str], None] = 'a7f3b2c81d40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSION = get_dimension()


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # pgvector is only meaningful on PostgreSQL. Enable the extension before the
    # vector column is created so the type is known to the server.
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column("chunks", sa.Column("embedding_model", sa.String(), nullable=True))
    op.add_column("chunks", sa.Column("embedding_dimension", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("embedded_content_hash", sa.String(), nullable=True))
    op.add_column("chunks", sa.Column("embedded_at", sa.DateTime(), nullable=True))

    if is_postgres:
        op.add_column("chunks", sa.Column("embedding", sa.Text(), nullable=True))
        op.execute(
            f"ALTER TABLE chunks ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSION}) "
            f"USING embedding::vector"
        )
    else:
        # SQLite/dev fallback: store the vector as JSON text.
        op.add_column("chunks", sa.Column("embedding", sa.Text(), nullable=True))

    op.create_index(
        op.f("ix_chunks_embedded_content_hash"),
        "chunks",
        ["embedded_content_hash"],
        unique=False,
    )

    # Approximate-nearest-neighbour index for cosine similarity queries.
    if is_postgres:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_cosine ON chunks "
            "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_cosine")

    op.drop_index(op.f("ix_chunks_embedded_content_hash"), table_name="chunks")
    op.drop_column("chunks", "embedding")
    op.drop_column("chunks", "embedded_at")
    op.drop_column("chunks", "embedded_content_hash")
    op.drop_column("chunks", "embedding_dimension")
    op.drop_column("chunks", "embedding_model")
