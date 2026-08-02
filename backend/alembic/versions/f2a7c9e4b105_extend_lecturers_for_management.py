"""Extend lecturers for institution-scoped management.

Revision ID: f2a7c9e4b105
Revises: e0a6b2c8f537
Create Date: 2026-08-02
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "f2a7c9e4b105"
down_revision: str | Sequence[str] | None = "e0a6b2c8f537"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lecturers", sa.Column("academic_rank", sa.String(length=30), nullable=True))
    op.add_column("lecturers", sa.Column("employment_date", sa.Date(), nullable=True))
    op.add_column("lecturers", sa.Column("office_location", sa.String(length=255), nullable=True))
    op.execute("UPDATE lecturers SET academic_rank = 'lecturer_ii' WHERE academic_rank IS NULL")
    op.alter_column("lecturers", "academic_rank", existing_type=sa.String(length=30), nullable=False)


def downgrade() -> None:
    op.drop_column("lecturers", "office_location")
    op.drop_column("lecturers", "employment_date")
    op.drop_column("lecturers", "academic_rank")
