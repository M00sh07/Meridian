"""add_commit_file_changes

Revision ID: c1d63ce49184
Revises: c4e8a1d9276b
Create Date: 2026-09-20 00:37:50.137114

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d63ce49184'
down_revision: Union[str, Sequence[str], None] = 'c4e8a1d9276b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "commit_file_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("commit_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("previous_path", sa.String(), nullable=True),
        sa.Column("change_type", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["commit_id"], ["commits.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_commit_file_changes_commit_id"), "commit_file_changes", ["commit_id"], unique=False)
    op.create_index(op.f("ix_commit_file_changes_file_id"), "commit_file_changes", ["file_id"], unique=False)
    op.create_index(op.f("ix_commit_file_changes_id"), "commit_file_changes", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_commit_file_changes_id"), table_name="commit_file_changes")
    op.drop_index(op.f("ix_commit_file_changes_file_id"), table_name="commit_file_changes")
    op.drop_index(op.f("ix_commit_file_changes_commit_id"), table_name="commit_file_changes")
    op.drop_table("commit_file_changes")

