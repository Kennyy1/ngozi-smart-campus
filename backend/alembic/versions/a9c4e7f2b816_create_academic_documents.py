"""Create institution-scoped academic documents.

Revision ID: a9c4e7f2b816
Revises: f6a9c2d4e817
Create Date: 2026-08-14
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a9c4e7f2b816"
down_revision: str | Sequence[str] | None = "f6a9c2d4e817"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "academic_documents",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("programme_id", sa.UUID(), nullable=True),
        sa.Column("graduation_record_id", sa.UUID(), nullable=True),
        sa.Column("official_transcript_id", sa.UUID(), nullable=True),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("document_reference", sa.String(40), nullable=False),
        sa.Column("verification_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("snapshot_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by_user_id", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.UUID(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("file_reference", sa.String(500), nullable=True),
        sa.Column("file_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("document_type IN ('certificate', 'statement_of_result')", name=op.f("ck_academic_documents_academic_document_type")),
        sa.CheckConstraint("status IN ('draft', 'issued', 'revoked', 'inactive')", name=op.f("ck_academic_documents_academic_document_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_academic_documents_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_academic_documents_student_id_students"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], name=op.f("fk_academic_documents_programme_id_programmes"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["graduation_record_id"], ["graduation_records.id"], name=op.f("fk_academic_documents_graduation_record_id_graduation_records"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["official_transcript_id"], ["official_transcripts.id"], name=op.f("fk_academic_documents_official_transcript_id_official_transcripts"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"], name=op.f("fk_academic_documents_generated_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], name=op.f("fk_academic_documents_issued_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], name=op.f("fk_academic_documents_revoked_by_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academic_documents")),
        sa.UniqueConstraint("document_reference", name="uq_academic_documents_reference"),
        sa.UniqueConstraint("verification_code", name="uq_academic_documents_verification_code"),
    )
    for column in ("institution_id", "student_id", "programme_id", "document_type", "status", "document_reference", "verification_code", "graduation_record_id"):
        op.create_index(op.f(f"ix_academic_documents_{column}"), "academic_documents", [column], unique=False)


def downgrade() -> None:
    for column in reversed(("institution_id", "student_id", "programme_id", "document_type", "status", "document_reference", "verification_code", "graduation_record_id")):
        op.drop_index(op.f(f"ix_academic_documents_{column}"), table_name="academic_documents")
    op.drop_table("academic_documents")
