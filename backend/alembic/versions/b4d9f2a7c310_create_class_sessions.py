"""Create class sessions.

Revision ID: b4d9f2a7c310
Revises: a3c8e1f6d209
Create Date: 2026-08-02
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "b4d9f2a7c310"
down_revision: str | Sequence[str] | None = "a3c8e1f6d209"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("class_sessions",
        sa.Column("institution_id", sa.UUID(), nullable=False), sa.Column("course_offering_id", sa.UUID(), nullable=False), sa.Column("lecturer_assignment_id", sa.UUID(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False), sa.Column("start_time", sa.Time(), nullable=False), sa.Column("end_time", sa.Time(), nullable=False), sa.Column("session_type", sa.String(30), nullable=False), sa.Column("topic", sa.String(255), nullable=False), sa.Column("venue", sa.String(255), nullable=True), sa.Column("delivery_mode", sa.String(30), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("start_time < end_time", name=op.f("ck_class_sessions_class_session_time_range")), sa.CheckConstraint("session_type IN ('lecture', 'tutorial', 'laboratory', 'practical', 'seminar')", name=op.f("ck_class_sessions_class_session_type")), sa.CheckConstraint("delivery_mode IN ('physical', 'online', 'hybrid')", name=op.f("ck_class_sessions_class_session_delivery_mode")), sa.CheckConstraint("status IN ('scheduled', 'completed', 'cancelled', 'postponed', 'inactive')", name=op.f("ck_class_sessions_class_session_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_class_sessions_institution_id_institutions"), ondelete="CASCADE"), sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], name=op.f("fk_class_sessions_course_offering_id_course_offerings"), ondelete="RESTRICT"), sa.ForeignKeyConstraint(["lecturer_assignment_id"], ["lecturer_assignments.id"], name=op.f("fk_class_sessions_lecturer_assignment_id_lecturer_assignments"), ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id", name=op.f("pk_class_sessions")))
    for column in ("institution_id", "course_offering_id", "lecturer_assignment_id", "session_date", "session_type", "delivery_mode", "status"): op.create_index(op.f(f"ix_class_sessions_{column}"), "class_sessions", [column], unique=False)
    op.create_index("uq_class_sessions_active_exact_slot", "class_sessions", ["course_offering_id", "session_date", "start_time", "end_time"], unique=True, postgresql_where=sa.text("status IN ('scheduled', 'completed')"))

def downgrade() -> None:
    op.drop_index("uq_class_sessions_active_exact_slot", table_name="class_sessions", postgresql_where=sa.text("status IN ('scheduled', 'completed')"))
    for column in reversed(("institution_id", "course_offering_id", "lecturer_assignment_id", "session_date", "session_type", "delivery_mode", "status")): op.drop_index(op.f(f"ix_class_sessions_{column}"), table_name="class_sessions")
    op.drop_table("class_sessions")
