"""Create assessment components.

Revision ID: e7b1c4d9a620
Revises: c6e8a2f4d901
Create Date: 2026-08-05
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e7b1c4d9a620"
down_revision: str | Sequence[str] | None = "c6e8a2f4d901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_components",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("course_offering_id", sa.UUID(), nullable=False),
        sa.Column("lecturer_assignment_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("assessment_type", sa.String(30), nullable=False),
        sa.Column("maximum_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("weight_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("assessment_type IN ('attendance', 'quiz', 'assignment', 'test', 'project', 'presentation', 'laboratory', 'practical', 'mid_semester', 'other')", name=op.f("ck_assessment_components_assessment_component_type")),
        sa.CheckConstraint("status IN ('draft', 'published', 'closed', 'cancelled', 'inactive')", name=op.f("ck_assessment_components_assessment_component_status")),
        sa.CheckConstraint("maximum_score > 0", name=op.f("ck_assessment_components_assessment_component_maximum_score")),
        sa.CheckConstraint("weight_percentage > 0 AND weight_percentage <= 100", name=op.f("ck_assessment_components_assessment_component_weight_percentage")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_assessment_components_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], name=op.f("fk_assessment_components_course_offering_id_course_offerings"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lecturer_assignment_id"], ["lecturer_assignments.id"], name=op.f("fk_assessment_components_lecturer_assignment_id_lecturer_assignments"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_components")),
    )
    for column in ("institution_id", "course_offering_id", "lecturer_assignment_id", "assessment_type", "scheduled_date", "status"):
        op.create_index(op.f(f"ix_assessment_components_{column}"), "assessment_components", [column], unique=False)
    op.create_index(
        "uq_assessment_components_offering_normalized_title",
        "assessment_components",
        ["course_offering_id", sa.text("lower(btrim(title))")],
        unique=True,
        postgresql_where=sa.text("status != 'inactive'"),
    )


def downgrade() -> None:
    op.drop_index("uq_assessment_components_offering_normalized_title", table_name="assessment_components", postgresql_where=sa.text("status != 'inactive'"))
    for column in reversed(("institution_id", "course_offering_id", "lecturer_assignment_id", "assessment_type", "scheduled_date", "status")):
        op.drop_index(op.f(f"ix_assessment_components_{column}"), table_name="assessment_components")
    op.drop_table("assessment_components")
