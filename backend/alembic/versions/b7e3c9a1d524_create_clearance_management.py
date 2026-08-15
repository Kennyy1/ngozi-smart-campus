"""Create institution-scoped clearance management.

Revision ID: b7e3c9a1d524
Revises: a9c4e7f2b816
Create Date: 2026-08-15
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b7e3c9a1d524"
down_revision: str | Sequence[str] | None = "a9c4e7f2b816"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clearance_requirements",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sequence_number > 0", name=op.f("ck_clearance_requirements_clearance_requirement_sequence_number")),
        sa.CheckConstraint("status IN ('active', 'inactive')", name=op.f("ck_clearance_requirements_clearance_requirement_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_clearance_requirements_institution_id_institutions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clearance_requirements")),
        sa.UniqueConstraint("institution_id", "code", name="uq_clearance_requirements_institution_code"),
    )
    for column in ("institution_id", "code", "status", "is_mandatory", "sequence_number"):
        op.create_index(op.f(f"ix_clearance_requirements_{column}"), "clearance_requirements", [column], unique=False)

    op.create_table(
        "student_clearances",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("clearance_requirement_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("evidence_reference", sa.String(500), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'cleared', 'rejected', 'waived', 'inactive')", name=op.f("ck_student_clearances_student_clearance_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_student_clearances_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_student_clearances_student_id_students"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["clearance_requirement_id"], ["clearance_requirements.id"], name=op.f("fk_student_clearances_clearance_requirement_id_clearance_requirements"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], name=op.f("fk_student_clearances_reviewed_by_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_clearances")),
    )
    for column in ("institution_id", "student_id", "clearance_requirement_id", "status", "reviewed_by_user_id"):
        op.create_index(op.f(f"ix_student_clearances_{column}"), "student_clearances", [column], unique=False)
    op.create_index(
        "uq_student_clearances_active_student_requirement", "student_clearances",
        ["student_id", "clearance_requirement_id"], unique=True,
        postgresql_where=sa.text("status <> 'inactive'"),
    )


def downgrade() -> None:
    op.drop_index("uq_student_clearances_active_student_requirement", table_name="student_clearances")
    for column in reversed(("institution_id", "student_id", "clearance_requirement_id", "status", "reviewed_by_user_id")):
        op.drop_index(op.f(f"ix_student_clearances_{column}"), table_name="student_clearances")
    op.drop_table("student_clearances")
    for column in reversed(("institution_id", "code", "status", "is_mandatory", "sequence_number")):
        op.drop_index(op.f(f"ix_clearance_requirements_{column}"), table_name="clearance_requirements")
    op.drop_table("clearance_requirements")
