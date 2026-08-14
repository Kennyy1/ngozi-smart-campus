"""Create administrative graduation records.

Revision ID: f6a9c2d4e817
Revises: d4f6a8c2e915
Create Date: 2026-08-14
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6a9c2d4e817"
down_revision: str | Sequence[str] | None = "d4f6a8c2e915"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "graduation_records",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("programme_id", sa.UUID(), nullable=False),
        sa.Column("graduation_reference", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("graduation_date", sa.Date(), nullable=True),
        sa.Column("award_title", sa.String(300), nullable=False),
        sa.Column("degree_classification", sa.String(50), nullable=True),
        sa.Column("degree_classification_label", sa.String(150), nullable=True),
        sa.Column("final_cgpa", sa.Numeric(4, 2), nullable=False),
        sa.Column("academic_standing", sa.String(50), nullable=False),
        sa.Column("eligibility_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("outcome_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prepared_by_user_id", sa.UUID(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.UUID(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("previous_student_enrollment_status", sa.String(30), nullable=True),
        sa.Column("previous_student_graduation_date", sa.Date(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'confirmed', 'revoked', 'inactive')", name=op.f("ck_graduation_records_graduation_record_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_graduation_records_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_graduation_records_student_id_students"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], name=op.f("fk_graduation_records_programme_id_programmes"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["prepared_by_user_id"], ["users.id"], name=op.f("fk_graduation_records_prepared_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["users.id"], name=op.f("fk_graduation_records_confirmed_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], name=op.f("fk_graduation_records_revoked_by_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_graduation_records")),
        sa.UniqueConstraint("graduation_reference", name="uq_graduation_records_reference"),
    )
    for column in ("institution_id", "student_id", "programme_id", "graduation_reference", "status", "graduation_date", "degree_classification", "prepared_by_user_id", "confirmed_by_user_id", "revoked_by_user_id"):
        op.create_index(op.f(f"ix_graduation_records_{column}"), "graduation_records", [column], unique=False)
    op.create_index(
        "uq_graduation_records_active_student_programme",
        "graduation_records", ["institution_id", "student_id", "programme_id"],
        unique=True, postgresql_where=sa.text("status IN ('draft', 'confirmed')"),
    )


def downgrade() -> None:
    op.drop_index("uq_graduation_records_active_student_programme", table_name="graduation_records")
    for column in reversed(("institution_id", "student_id", "programme_id", "graduation_reference", "status", "graduation_date", "degree_classification", "prepared_by_user_id", "confirmed_by_user_id", "revoked_by_user_id")):
        op.drop_index(op.f(f"ix_graduation_records_{column}"), table_name="graduation_records")
    op.drop_table("graduation_records")
