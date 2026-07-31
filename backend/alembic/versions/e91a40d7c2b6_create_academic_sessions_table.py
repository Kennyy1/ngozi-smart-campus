"""Create academic sessions table.

Revision ID: e91a40d7c2b6
Revises: d42f6a8b913e
Create Date: 2026-07-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e91a40d7c2b6"
down_revision: str | Sequence[str] | None = "d42f6a8b913e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "academic_sessions",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "start_date < end_date",
            name=op.f("ck_academic_sessions_academic_session_date_range"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name=op.f("ck_academic_sessions_academic_session_status"),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name=op.f(
                "fk_academic_sessions_institution_id_institutions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academic_sessions")),
        sa.UniqueConstraint(
            "institution_id",
            "name",
            name="uq_academic_sessions_institution_name",
        ),
    )
    op.create_index(
        op.f("ix_academic_sessions_institution_id"),
        "academic_sessions",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        "uq_academic_sessions_current_institution",
        "academic_sessions",
        ["institution_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_academic_sessions_current_institution",
        table_name="academic_sessions",
        postgresql_where=sa.text("is_current"),
    )
    op.drop_index(
        op.f("ix_academic_sessions_institution_id"),
        table_name="academic_sessions",
    )
    op.drop_table("academic_sessions")
