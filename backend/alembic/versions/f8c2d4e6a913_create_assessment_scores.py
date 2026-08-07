"""Create assessment scores.

Revision ID: f8c2d4e6a913
Revises: e7b1c4d9a620
Create Date: 2026-08-07
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f8c2d4e6a913"
down_revision: str | Sequence[str] | None = "e7b1c4d9a620"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_scores",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("assessment_component_id", sa.UUID(), nullable=False),
        sa.Column("course_registration_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Numeric(10, 2), nullable=False),
        sa.Column("graded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score >= 0", name=op.f("ck_assessment_scores_assessment_score_score")),
        sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_assessment_scores_assessment_score_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_assessment_scores_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_component_id"], ["assessment_components.id"], name=op.f("fk_assessment_scores_assessment_component_id_assessment_components"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_registration_id"], ["course_registrations.id"], name=op.f("fk_assessment_scores_course_registration_id_course_registrations"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["graded_by_user_id"], ["users.id"], name=op.f("fk_assessment_scores_graded_by_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_scores")),
    )
    for column in (
        "institution_id",
        "assessment_component_id",
        "course_registration_id",
        "graded_by_user_id",
        "graded_at",
        "status",
    ):
        op.create_index(op.f(f"ix_assessment_scores_{column}"), "assessment_scores", [column], unique=False)
    op.create_index(
        "uq_assessment_scores_active_component_registration",
        "assessment_scores",
        ["assessment_component_id", "course_registration_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_assessment_scores_active_component_registration",
        table_name="assessment_scores",
        postgresql_where=sa.text("status = 'active'"),
    )
    for column in reversed((
        "institution_id",
        "assessment_component_id",
        "course_registration_id",
        "graded_by_user_id",
        "graded_at",
        "status",
    )):
        op.drop_index(op.f(f"ix_assessment_scores_{column}"), table_name="assessment_scores")
    op.drop_table("assessment_scores")
