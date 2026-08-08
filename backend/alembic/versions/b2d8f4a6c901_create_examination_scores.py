"""Create examination scores.

Revision ID: b2d8f4a6c901
Revises: a1c9e7d5b302
Create Date: 2026-08-08
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b2d8f4a6c901"
down_revision: str | Sequence[str] | None = "a1c9e7d5b302"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "examination_scores",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("examination_id", sa.UUID(), nullable=False),
        sa.Column("course_registration_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Numeric(10, 2), nullable=False),
        sa.Column("graded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score >= 0", name=op.f("ck_examination_scores_examination_score_score")),
        sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_examination_scores_examination_score_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_examination_scores_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["examination_id"], ["examinations.id"], name=op.f("fk_examination_scores_examination_id_examinations"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_registration_id"], ["course_registrations.id"], name=op.f("fk_examination_scores_course_registration_id_course_registrations"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["graded_by_user_id"], ["users.id"], name=op.f("fk_examination_scores_graded_by_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_examination_scores")),
    )
    for column in ("institution_id", "examination_id", "course_registration_id", "graded_by_user_id", "graded_at", "status"):
        op.create_index(op.f(f"ix_examination_scores_{column}"), "examination_scores", [column], unique=False)
    op.create_index("uq_examination_scores_active_examination_registration", "examination_scores", ["examination_id", "course_registration_id"], unique=True, postgresql_where=sa.text("status = 'active'"))


def downgrade() -> None:
    op.drop_index("uq_examination_scores_active_examination_registration", table_name="examination_scores", postgresql_where=sa.text("status = 'active'"))
    for column in reversed(("institution_id", "examination_id", "course_registration_id", "graded_by_user_id", "graded_at", "status")):
        op.drop_index(op.f(f"ix_examination_scores_{column}"), table_name="examination_scores")
    op.drop_table("examination_scores")
