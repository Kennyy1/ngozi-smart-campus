"""Align departments table with the department management module.

Revision ID: c9184e02a711
Revises: b70633d9bd22
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op


revision: str = "c9184e02a711"
down_revision: str | Sequence[str] | None = "b70633d9bd22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_departments_department_status",
        "departments",
        "status IN ('active', 'inactive')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_departments_department_status",
        "departments",
        type_="check",
    )
