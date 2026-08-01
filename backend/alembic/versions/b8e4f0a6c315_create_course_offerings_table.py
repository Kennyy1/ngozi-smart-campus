"""Create course offerings table.

Revision ID: b8e4f0a6c315
Revises: c7d3e9f5b204
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b8e4f0a6c315"
down_revision: str | Sequence[str] | None = "c7d3e9f5b204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_offerings",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("course_id", sa.UUID(), nullable=False),
        sa.Column("academic_session_id", sa.UUID(), nullable=False),
        sa.Column("semester_id", sa.UUID(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("registration_open", sa.Boolean(), nullable=False),
        sa.Column("registration_start_date", sa.Date(), nullable=True),
        sa.Column("registration_end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("capacity IS NULL OR capacity > 0", name=op.f("ck_course_offerings_course_offering_capacity")),
        sa.CheckConstraint("registration_start_date IS NULL OR registration_end_date IS NULL OR registration_start_date < registration_end_date", name=op.f("ck_course_offerings_course_offering_registration_window")),
        sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_course_offerings_course_offering_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_course_offerings_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name=op.f("fk_course_offerings_course_id_courses"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_session_id"], ["academic_sessions.id"], name=op.f("fk_course_offerings_academic_session_id_academic_sessions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["semester_id"], ["semesters.id"], name=op.f("fk_course_offerings_semester_id_semesters"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_offerings")),
        sa.UniqueConstraint("course_id", "academic_session_id", "semester_id", name="uq_course_offerings_course_session_semester"),
    )
    op.create_index(op.f("ix_course_offerings_institution_id"), "course_offerings", ["institution_id"], unique=False)
    op.create_index(op.f("ix_course_offerings_course_id"), "course_offerings", ["course_id"], unique=False)
    op.create_index(op.f("ix_course_offerings_academic_session_id"), "course_offerings", ["academic_session_id"], unique=False)
    op.create_index(op.f("ix_course_offerings_semester_id"), "course_offerings", ["semester_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_course_offerings_semester_id"), table_name="course_offerings")
    op.drop_index(op.f("ix_course_offerings_academic_session_id"), table_name="course_offerings")
    op.drop_index(op.f("ix_course_offerings_course_id"), table_name="course_offerings")
    op.drop_index(op.f("ix_course_offerings_institution_id"), table_name="course_offerings")
    op.drop_table("course_offerings")
