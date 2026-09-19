"""Add file import dependencies

Revision ID: 8b7d2f1c4e6a
Revises: 457922a70e92
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8b7d2f1c4e6a"
down_revision: Union[str, Sequence[str], None] = "457922a70e92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dependencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_file_id", sa.Integer(), nullable=False),
        sa.Column("target_file_id", sa.Integer(), nullable=True),
        sa.Column("imported_module", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["source_file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["target_file_id"], ["files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dependencies_id"), "dependencies", ["id"], unique=False)
    op.create_index(
        op.f("ix_dependencies_source_file_id"),
        "dependencies",
        ["source_file_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dependencies_target_file_id"),
        "dependencies",
        ["target_file_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_dependencies_target_file_id"), table_name="dependencies")
    op.drop_index(op.f("ix_dependencies_source_file_id"), table_name="dependencies")
    op.drop_index(op.f("ix_dependencies_id"), table_name="dependencies")
    op.drop_table("dependencies")
