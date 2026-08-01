"""Add Student Programme foreign key.

Revision ID: e0a6b2c8f537
Revises: d9f5a1b7e426
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op


revision: str = "e0a6b2c8f537"
down_revision: str | Sequence[str] | None = "d9f5a1b7e426"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_students_programme_id_programmes",
        "students",
        "programmes",
        ["programme_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_students_programme_id_programmes",
        "students",
        type_="foreignkey",
    )
