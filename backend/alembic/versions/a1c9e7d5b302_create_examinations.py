"""Create examinations.

Revision ID: a1c9e7d5b302
Revises: f8c2d4e6a913
Create Date: 2026-08-08
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a1c9e7d5b302"
down_revision: str | Sequence[str] | None = "f8c2d4e6a913"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "examinations",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("course_offering_id", sa.UUID(), nullable=False),
        sa.Column("lecturer_assignment_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("examination_type", sa.String(30), nullable=False),
        sa.Column("maximum_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("weight_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("venue", sa.String(255), nullable=True),
        sa.Column("delivery_mode", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("examination_type IN ('written', 'practical', 'oral', 'project_defense', 'clinical', 'other')", name=op.f("ck_examinations_examination_type")),
        sa.CheckConstraint("delivery_mode IN ('physical', 'online', 'hybrid')", name=op.f("ck_examinations_examination_delivery_mode")),
        sa.CheckConstraint("status IN ('draft', 'scheduled', 'completed', 'cancelled', 'postponed', 'inactive')", name=op.f("ck_examinations_examination_status")),
        sa.CheckConstraint("maximum_score > 0", name=op.f("ck_examinations_examination_maximum_score")),
        sa.CheckConstraint("weight_percentage > 0 AND weight_percentage <= 100", name=op.f("ck_examinations_examination_weight_percentage")),
        sa.CheckConstraint("start_time < end_time", name=op.f("ck_examinations_examination_times")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_examinations_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], name=op.f("fk_examinations_course_offering_id_course_offerings"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lecturer_assignment_id"], ["lecturer_assignments.id"], name=op.f("fk_examinations_lecturer_assignment_id_lecturer_assignments"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_examinations")),
    )
    for column in ("institution_id", "course_offering_id", "lecturer_assignment_id", "examination_type", "exam_date", "delivery_mode", "status"):
        op.create_index(op.f(f"ix_examinations_{column}"), "examinations", [column], unique=False)
    op.create_index("uq_examinations_offering_normalized_title", "examinations", ["course_offering_id", sa.text("lower(btrim(title))")], unique=True, postgresql_where=sa.text("status != 'inactive'"))


def downgrade() -> None:
    op.drop_index("uq_examinations_offering_normalized_title", table_name="examinations", postgresql_where=sa.text("status != 'inactive'"))
    for column in reversed(("institution_id", "course_offering_id", "lecturer_assignment_id", "examination_type", "exam_date", "delivery_mode", "status")):
        op.drop_index(op.f(f"ix_examinations_{column}"), table_name="examinations")
    op.drop_table("examinations")
