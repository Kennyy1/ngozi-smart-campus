"""Create official transcript snapshots.

Revision ID: d4f6a8c2e915
Revises: c3e9a1f7b204
Create Date: 2026-08-12
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4f6a8c2e915"
down_revision: str | Sequence[str] | None = "c3e9a1f7b204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "official_transcripts",
        sa.Column("institution_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("programme_id", sa.UUID(), nullable=False),
        sa.Column("transcript_reference", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("snapshot_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by_user_id", sa.UUID(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_by_user_id", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.UUID(), nullable=True),
        sa.Column("revocation_reason", sa.Text(), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'issued', 'revoked', 'inactive')", name=op.f("ck_official_transcripts_official_transcript_status")),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], name=op.f("fk_official_transcripts_institution_id_institutions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_official_transcripts_student_id_students"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["programme_id"], ["programmes.id"], name=op.f("fk_official_transcripts_programme_id_programmes"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"], name=op.f("fk_official_transcripts_generated_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by_user_id"], ["users.id"], name=op.f("fk_official_transcripts_issued_by_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], name=op.f("fk_official_transcripts_revoked_by_user_id_users"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_official_transcripts")),
        sa.UniqueConstraint("institution_id", "transcript_reference", name="uq_official_transcripts_institution_reference"),
    )
    for column in ("institution_id", "student_id", "programme_id", "transcript_reference", "status", "generated_by_user_id", "issued_by_user_id"):
        op.create_index(op.f(f"ix_official_transcripts_{column}"), "official_transcripts", [column], unique=False)


def downgrade() -> None:
    for column in reversed(("institution_id", "student_id", "programme_id", "transcript_reference", "status", "generated_by_user_id", "issued_by_user_id")):
        op.drop_index(op.f(f"ix_official_transcripts_{column}"), table_name="official_transcripts")
    op.drop_table("official_transcripts")
