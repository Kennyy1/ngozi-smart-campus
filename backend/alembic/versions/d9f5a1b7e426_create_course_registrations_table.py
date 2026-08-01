"""Create course registrations table.

Revision ID: d9f5a1b7e426
Revises: b8e4f0a6c315
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d9f5a1b7e426"
down_revision: str | Sequence[str] | None = "b8e4f0a6c315"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_registrations",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("course_offering_id", sa.UUID(), nullable=False),
        sa.Column("registration_status", sa.String(length=30), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dropped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("registration_status IN ('registered', 'dropped')", name=op.f("ck_course_registrations_course_registration_registration_status")),
        sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_course_registrations_course_registration_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_course_registrations_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_course_registrations_student_id_students"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], name=op.f("fk_course_registrations_course_offering_id_course_offerings"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_registrations")),
    )
    op.create_index(op.f("ix_course_registrations_institution_id"), "course_registrations", ["institution_id"], unique=False)
    op.create_index(op.f("ix_course_registrations_student_id"), "course_registrations", ["student_id"], unique=False)
    op.create_index(op.f("ix_course_registrations_course_offering_id"), "course_registrations", ["course_offering_id"], unique=False)
    op.create_index(op.f("ix_course_registrations_registration_status"), "course_registrations", ["registration_status"], unique=False)
    op.create_index("uq_course_registrations_active_student_offering", "course_registrations", ["student_id", "course_offering_id"], unique=True, postgresql_where=sa.text("status = 'active'"))


def downgrade() -> None:
    op.drop_index("uq_course_registrations_active_student_offering", table_name="course_registrations", postgresql_where=sa.text("status = 'active'"))
    op.drop_index(op.f("ix_course_registrations_registration_status"), table_name="course_registrations")
    op.drop_index(op.f("ix_course_registrations_course_offering_id"), table_name="course_registrations")
    op.drop_index(op.f("ix_course_registrations_student_id"), table_name="course_registrations")
    op.drop_index(op.f("ix_course_registrations_institution_id"), table_name="course_registrations")
    op.drop_table("course_registrations")
