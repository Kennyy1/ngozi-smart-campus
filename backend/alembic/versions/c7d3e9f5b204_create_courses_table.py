"""Create courses table.

Revision ID: c7d3e9f5b204
Revises: f4b2d8e6a901
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c7d3e9f5b204"
down_revision: str | Sequence[str] | None = "f4b2d8e6a901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("programme_id", sa.UUID(), nullable=False),
        sa.Column("academic_level_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("credit_units", sa.Integer(), nullable=False),
        sa.Column("course_type", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("credit_units > 0", name=op.f("ck_courses_course_credit_units")),
        sa.CheckConstraint("course_type IN ('compulsory', 'elective', 'required', 'general')", name=op.f("ck_courses_course_type")),
        sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_courses_course_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_courses_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name=op.f("fk_courses_department_id_departments"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], name=op.f("fk_courses_programme_id_programmes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_level_id"], ["academic_levels.id"], name=op.f("fk_courses_academic_level_id_academic_levels"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_courses")),
        sa.UniqueConstraint("institution_id", "code", name="uq_courses_institution_code"),
        sa.UniqueConstraint("programme_id", "academic_level_id", "title", name="uq_courses_programme_level_title"),
    )
    op.create_index(op.f("ix_courses_institution_id"), "courses", ["institution_id"], unique=False)
    op.create_index(op.f("ix_courses_department_id"), "courses", ["department_id"], unique=False)
    op.create_index(op.f("ix_courses_programme_id"), "courses", ["programme_id"], unique=False)
    op.create_index(op.f("ix_courses_academic_level_id"), "courses", ["academic_level_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_courses_academic_level_id"), table_name="courses")
    op.drop_index(op.f("ix_courses_programme_id"), table_name="courses")
    op.drop_index(op.f("ix_courses_department_id"), table_name="courses")
    op.drop_index(op.f("ix_courses_institution_id"), table_name="courses")
    op.drop_table("courses")
