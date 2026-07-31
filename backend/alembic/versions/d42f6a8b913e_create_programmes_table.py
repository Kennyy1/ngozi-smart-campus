"""Create programmes table.

Revision ID: d42f6a8b913e
Revises: c9184e02a711
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d42f6a8b913e"
down_revision: str | Sequence[str] | None = "c9184e02a711"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "programmes",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("faculty_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("award", sa.String(length=20), nullable=False),
        sa.Column("duration_years", sa.Integer(), nullable=False),
        sa.Column("study_mode", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "award IN ('BSc', 'BA', 'BEng', 'MSc', 'MBA', 'PGD', 'MPhil', 'PhD')",
            name=op.f("ck_programmes_programme_award"),
        ),
        sa.CheckConstraint(
            "duration_years > 0",
            name=op.f("ck_programmes_programme_duration_years"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name=op.f("ck_programmes_programme_status"),
        ),
        sa.CheckConstraint(
            "study_mode IN ('FULL_TIME', 'PART_TIME', 'DISTANCE')",
            name=op.f("ck_programmes_programme_study_mode"),
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name=op.f("fk_programmes_department_id_departments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["faculty_id"],
            ["faculties.id"],
            name=op.f("fk_programmes_faculty_id_faculties"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name=op.f("fk_programmes_institution_id_institutions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programmes")),
        sa.UniqueConstraint(
            "department_id",
            "name",
            name="uq_programmes_department_name",
        ),
        sa.UniqueConstraint(
            "institution_id",
            "code",
            name="uq_programmes_institution_code",
        ),
    )
    op.create_index(
        op.f("ix_programmes_department_id"),
        "programmes",
        ["department_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_programmes_faculty_id"),
        "programmes",
        ["faculty_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_programmes_institution_id"),
        "programmes",
        ["institution_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_programmes_institution_id"), table_name="programmes")
    op.drop_index(op.f("ix_programmes_faculty_id"), table_name="programmes")
    op.drop_index(op.f("ix_programmes_department_id"), table_name="programmes")
    op.drop_table("programmes")
