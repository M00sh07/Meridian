"""add_chunks

Revision ID: a7f3b2c81d40
Revises: c1d63ce49184
Create Date: 2026-09-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7f3b2c81d40'
down_revision: Union[str, Sequence[str], None] = 'c1d63ce49184'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("symbol_id", sa.Integer(), nullable=True),
        sa.Column("chunk_key", sa.String(), nullable=False),
        sa.Column("chunk_type", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("symbol_name", sa.String(), nullable=True),
        sa.Column("symbol_type", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["symbol_id"], ["symbols.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "chunk_key", name="uq_chunks_repository_id_chunk_key"
        ),
    )
    op.create_index(op.f("ix_chunks_id"), "chunks", ["id"], unique=False)
    op.create_index(op.f("ix_chunks_repository_id"), "chunks", ["repository_id"], unique=False)
    op.create_index(op.f("ix_chunks_file_id"), "chunks", ["file_id"], unique=False)
    op.create_index(op.f("ix_chunks_symbol_id"), "chunks", ["symbol_id"], unique=False)
    op.create_index(op.f("ix_chunks_chunk_key"), "chunks", ["chunk_key"], unique=False)
    op.create_index(op.f("ix_chunks_path"), "chunks", ["path"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chunks_path"), table_name="chunks")
    op.drop_index(op.f("ix_chunks_chunk_key"), table_name="chunks")
    op.drop_index(op.f("ix_chunks_symbol_id"), table_name="chunks")
    op.drop_index(op.f("ix_chunks_file_id"), table_name="chunks")
    op.drop_index(op.f("ix_chunks_repository_id"), table_name="chunks")
    op.drop_index(op.f("ix_chunks_id"), table_name="chunks")
    op.drop_table("chunks")
