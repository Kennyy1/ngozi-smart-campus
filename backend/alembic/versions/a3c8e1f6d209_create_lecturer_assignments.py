"""Create lecturer assignments.

Revision ID: a3c8e1f6d209
Revises: f2a7c9e4b105
Create Date: 2026-08-02
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "a3c8e1f6d209"
down_revision: str | Sequence[str] | None = "f2a7c9e4b105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("lecturer_assignments",
        sa.Column("institution_id", sa.UUID(), nullable=False), sa.Column("lecturer_id", sa.UUID(), nullable=False), sa.Column("course_offering_id", sa.UUID(), nullable=False),
        sa.Column("assignment_role", sa.String(length=30), nullable=False), sa.Column("is_primary", sa.Boolean(), nullable=False), sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True), sa.Column("status", sa.String(length=30), nullable=False), sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("assignment_role IN ('primary', 'co_instructor', 'teaching_assistant', 'lab_instructor')", name=op.f("ck_lecturer_assignments_lecturer_assignment_role")), sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_lecturer_assignments_lecturer_assignment_status")), sa.CheckConstraint("ended_at IS NULL OR assigned_at < ended_at", name=op.f("ck_lecturer_assignments_lecturer_assignment_dates")), sa.CheckConstraint("(assignment_role = 'primary' AND is_primary) OR (assignment_role != 'primary' AND NOT is_primary)", name=op.f("ck_lecturer_assignments_lecturer_assignment_primary_role")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_lecturer_assignments_institution_id_institutions"), ondelete="CASCADE"), sa.ForeignKeyConstraint(["lecturer_id"], ["lecturers.id"], name=op.f("fk_lecturer_assignments_lecturer_id_lecturers"), ondelete="RESTRICT"), sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], name=op.f("fk_lecturer_assignments_course_offering_id_course_offerings"), ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id", name=op.f("pk_lecturer_assignments")))
    for column in ("institution_id", "lecturer_id", "course_offering_id", "assignment_role"): op.create_index(op.f(f"ix_lecturer_assignments_{column}"), "lecturer_assignments", [column], unique=False)
    op.create_index("uq_lecturer_assignments_active_lecturer_offering", "lecturer_assignments", ["lecturer_id", "course_offering_id"], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_index("uq_lecturer_assignments_active_primary_offering", "lecturer_assignments", ["course_offering_id"], unique=True, postgresql_where=sa.text("status = 'active' AND is_primary"))


def downgrade() -> None:
    op.drop_index("uq_lecturer_assignments_active_primary_offering", table_name="lecturer_assignments", postgresql_where=sa.text("status = 'active' AND is_primary")); op.drop_index("uq_lecturer_assignments_active_lecturer_offering", table_name="lecturer_assignments", postgresql_where=sa.text("status = 'active'"))
    for column in reversed(("institution_id", "lecturer_id", "course_offering_id", "assignment_role")): op.drop_index(op.f(f"ix_lecturer_assignments_{column}"), table_name="lecturer_assignments")
    op.drop_table("lecturer_assignments")
