"""Create academic levels table.

Revision ID: f4b2d8e6a901
Revises: a9e5c1d7f302
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f4b2d8e6a901"
down_revision: str | Sequence[str] | None = "a9e5c1d7f302"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "academic_levels",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("programme_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
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
            "sequence_number > 0",
            name=op.f("ck_academic_levels_academic_level_sequence_number"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')",
            name=op.f("ck_academic_levels_academic_level_status"),
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name=op.f("fk_academic_levels_institution_id_institutions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["programme_id"],
            ["programmes.id"],
            name=op.f("fk_academic_levels_programme_id_programmes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academic_levels")),
        sa.UniqueConstraint(
            "programme_id",
            "name",
            name="uq_academic_levels_programme_name",
        ),
        sa.UniqueConstraint(
            "programme_id",
            "code",
            name="uq_academic_levels_programme_code",
        ),
        sa.UniqueConstraint(
            "programme_id",
            "sequence_number",
            name="uq_academic_levels_programme_sequence",
        ),
    )
    op.create_index(
        op.f("ix_academic_levels_institution_id"),
        "academic_levels",
        ["institution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_academic_levels_programme_id"),
        "academic_levels",
        ["programme_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_academic_levels_programme_id"),
        table_name="academic_levels",
    )
    op.drop_index(
        op.f("ix_academic_levels_institution_id"),
        table_name="academic_levels",
    )
    op.drop_table("academic_levels")
