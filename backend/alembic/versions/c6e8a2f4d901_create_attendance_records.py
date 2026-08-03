"""Create attendance records.

Revision ID: c6e8a2f4d901
Revises: b4d9f2a7c310
Create Date: 2026-08-03
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c6e8a2f4d901"
down_revision: str | Sequence[str] | None = "b4d9f2a7c310"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_records",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("class_session_id", sa.UUID(), nullable=False),
        sa.Column("course_registration_id", sa.UUID(), nullable=False),
        sa.Column("attendance_status", sa.String(30), nullable=False),
        sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("attendance_status IN ('present', 'absent', 'late', 'excused')", name=op.f("ck_attendance_records_attendance_record_attendance_status")),
        sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_attendance_records_attendance_record_status")),
        sa.CheckConstraint("(attendance_status = 'late' AND check_in_time IS NOT NULL) OR (attendance_status IN ('absent', 'excused') AND check_in_time IS NULL) OR attendance_status = 'present'", name=op.f("ck_attendance_records_attendance_record_check_in_state")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_attendance_records_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_session_id"], ["class_sessions.id"], name=op.f("fk_attendance_records_class_session_id_class_sessions"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["course_registration_id"], ["course_registrations.id"], name=op.f("fk_attendance_records_course_registration_id_course_registrations"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recorded_by_user_id"], ["users.id"], name=op.f("fk_attendance_records_recorded_by_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_records")),
    )
    for column in ("institution_id", "class_session_id", "course_registration_id", "attendance_status", "recorded_by_user_id", "status"):
        op.create_index(op.f(f"ix_attendance_records_{column}"), "attendance_records", [column], unique=False)
    op.create_index(
        "uq_attendance_records_active_session_registration",
        "attendance_records",
        ["class_session_id", "course_registration_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_attendance_records_active_session_registration", table_name="attendance_records", postgresql_where=sa.text("status = 'active'"))
    for column in reversed(("institution_id", "class_session_id", "course_registration_id", "attendance_status", "recorded_by_user_id", "status")):
        op.drop_index(op.f(f"ix_attendance_records_{column}"), table_name="attendance_records")
    op.drop_table("attendance_records")
