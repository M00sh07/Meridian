"""Add repository commit history

Revision ID: c4e8a1d9276b
Revises: 8b7d2f1c4e6a
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8a1d9276b"
down_revision: Union[str, Sequence[str], None] = "8b7d2f1c4e6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("sha", sa.String(), nullable=False),
        sa.Column("author_name", sa.String(), nullable=True),
        sa.Column("author_email", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("committed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "sha"),
    )
    op.create_index(op.f("ix_commits_id"), "commits", ["id"], unique=False)
    op.create_index(
        op.f("ix_commits_repository_id"), "commits", ["repository_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_commits_repository_id"), table_name="commits")
    op.drop_index(op.f("ix_commits_id"), table_name="commits")
    op.drop_table("commits")