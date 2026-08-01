"""Create semesters table.

Revision ID: a9e5c1d7f302
Revises: e91a40d7c2b6
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "a9e5c1d7f302"
down_revision: str | Sequence[str] | None = "e91a40d7c2b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "semesters",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("academic_session_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("start_date < end_date", name=op.f("ck_semesters_semester_date_range")),
        sa.CheckConstraint("sequence_number > 0", name=op.f("ck_semesters_semester_sequence_number")),
        sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_semesters_semester_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_semesters_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_session_id"], ["academic_sessions.id"], name=op.f("fk_semesters_academic_session_id_academic_sessions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_semesters")),
        sa.UniqueConstraint("academic_session_id", "name", name="uq_semesters_academic_session_name"),
        sa.UniqueConstraint("academic_session_id", "sequence_number", name="uq_semesters_academic_session_sequence"),
    )
    op.create_index(op.f("ix_semesters_institution_id"), "semesters", ["institution_id"], unique=False)
    op.create_index(op.f("ix_semesters_academic_session_id"), "semesters", ["academic_session_id"], unique=False)
    op.create_index("uq_semesters_current_institution", "semesters", ["institution_id"], unique=True, postgresql_where=sa.text("is_current"))


def downgrade() -> None:
    op.drop_index("uq_semesters_current_institution", table_name="semesters", postgresql_where=sa.text("is_current"))
    op.drop_index(op.f("ix_semesters_academic_session_id"), table_name="semesters")
    op.drop_index(op.f("ix_semesters_institution_id"), table_name="semesters")
    op.drop_table("semesters")
