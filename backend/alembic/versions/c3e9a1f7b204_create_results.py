"""Create official result snapshots.

Revision ID: c3e9a1f7b204
Revises: b2d8f4a6c901
Create Date: 2026-08-11
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c3e9a1f7b204"
down_revision: str | Sequence[str] | None = "b2d8f4a6c901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "results",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("course_registration_id", sa.UUID(), nullable=False),
        sa.Column("course_offering_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("continuous_assessment_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("examination_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("final_score", sa.Numeric(10, 2), nullable=False),
        sa.Column("grade_letter", sa.String(5), nullable=False),
        sa.Column("grade_point", sa.Numeric(4, 2), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("computed_by_user_id", sa.UUID(), nullable=False),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("approved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("published_by_user_id", sa.UUID(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'published', 'withheld', 'inactive')", name=op.f("ck_results_result_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_results_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_registration_id"], ["course_registrations.id"], name=op.f("fk_results_course_registration_id_course_registrations"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], name=op.f("fk_results_course_offering_id_course_offerings"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_results_student_id_students"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["computed_by_user_id"], ["users.id"], name=op.f("fk_results_computed_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], name=op.f("fk_results_submitted_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], name=op.f("fk_results_approved_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"], name=op.f("fk_results_published_by_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_results")),
    )
    for column in ("institution_id", "course_registration_id", "course_offering_id", "student_id", "grade_letter", "passed", "status", "computed_by_user_id"):
        op.create_index(op.f(f"ix_results_{column}"), "results", [column], unique=False)
    op.create_index("uq_results_active_course_registration", "results", ["course_registration_id"], unique=True, postgresql_where=sa.text("status != 'inactive'"))


def downgrade() -> None:
    op.drop_index("uq_results_active_course_registration", table_name="results", postgresql_where=sa.text("status != 'inactive'"))
    for column in reversed(("institution_id", "course_registration_id", "course_offering_id", "student_id", "grade_letter", "passed", "status", "computed_by_user_id")):
        op.drop_index(op.f(f"ix_results_{column}"), table_name="results")
    op.drop_table("results")
