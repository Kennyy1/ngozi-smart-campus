"""Align faculties table with the faculty management module.

Revision ID: b70633d9bd22
Revises: acf35fcc8330
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op


revision: str = "b70633d9bd22"
down_revision: str | Sequence[str] | None = "acf35fcc8330"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_faculties_faculty_status",
        "faculties",
        "status IN ('active', 'inactive')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_faculties_faculty_status",
        "faculties",
        type_="check",
    )
