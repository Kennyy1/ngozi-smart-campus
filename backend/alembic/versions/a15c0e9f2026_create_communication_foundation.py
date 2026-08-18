"""create communication foundation

Revision ID: a15c0e9f2026
Revises: f9d2a6c4b817
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a15c0e9f2026"
down_revision: str | None = "f9d2a6c4b817"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade():
    op.create_table("announcements",
        sa.Column("institution_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("title",sa.String(255),nullable=False),sa.Column("body",sa.Text(),nullable=False),
        sa.Column("announcement_type",sa.String(30),nullable=False),sa.Column("audience_type",sa.String(30),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("priority",sa.String(20),nullable=False),
        sa.Column("published_at",sa.DateTime(timezone=True)),sa.Column("expires_at",sa.DateTime(timezone=True)),sa.Column("created_by_user_id",postgresql.UUID(as_uuid=True),nullable=False),
        sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.CheckConstraint("announcement_type IN ('general','academic','examination','timetable','event','emergency','administrative','course')",name=op.f("ck_announcements_announcement_type")),
        sa.CheckConstraint("audience_type IN ('all','students','lecturers','guardians','administrators','programme','academic_level','course_offering')",name=op.f("ck_announcements_announcement_audience")),
        sa.CheckConstraint("status IN ('draft','published','archived')",name=op.f("ck_announcements_announcement_status")),sa.CheckConstraint("priority IN ('normal','important','urgent')",name=op.f("ck_announcements_announcement_priority")),sa.CheckConstraint("expires_at IS NULL OR published_at IS NULL OR expires_at > published_at",name=op.f("ck_announcements_announcement_expiry")),
        sa.ForeignKeyConstraint(["institution_id"],["institutions.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["created_by_user_id"],["users.id"],ondelete="RESTRICT"),sa.PrimaryKeyConstraint("id"))
    for c in ("institution_id","audience_type","status","priority","published_at","expires_at"):op.create_index(op.f(f"ix_announcements_{c}"),"announcements",[c])
    op.create_table("announcement_targets",sa.Column("institution_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("announcement_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("target_type",sa.String(30),nullable=False),sa.Column("target_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),sa.ForeignKeyConstraint(["institution_id"],["institutions.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["announcement_id"],["announcements.id"],ondelete="CASCADE"),sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("announcement_id","target_type","target_id",name="uq_announcement_target"))
    for c in ("institution_id","announcement_id","target_id"):op.create_index(op.f(f"ix_announcement_targets_{c}"),"announcement_targets",[c])
    op.create_table("announcement_reads",sa.Column("institution_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("announcement_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("user_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("read_at",sa.DateTime(timezone=True),nullable=False),sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),sa.ForeignKeyConstraint(["institution_id"],["institutions.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["announcement_id"],["announcements.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"),sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("announcement_id","user_id",name="uq_announcement_read_user"))
    for c in ("institution_id","announcement_id","user_id"):op.create_index(op.f(f"ix_announcement_reads_{c}"),"announcement_reads",[c])
    op.create_table("notifications",sa.Column("institution_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("user_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("notification_type",sa.String(50),nullable=False),sa.Column("title",sa.String(255),nullable=False),sa.Column("message",sa.Text(),nullable=False),sa.Column("reference_type",sa.String(50)),sa.Column("reference_id",postgresql.UUID(as_uuid=True)),sa.Column("is_read",sa.Boolean(),nullable=False),sa.Column("read_at",sa.DateTime(timezone=True)),sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.ForeignKeyConstraint(["institution_id"],["institutions.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"),sa.PrimaryKeyConstraint("id"))
    for c in ("institution_id","user_id","notification_type","is_read"):op.create_index(op.f(f"ix_notifications_{c}"),"notifications",[c])

def downgrade():
    op.drop_table("notifications");op.drop_table("announcement_reads");op.drop_table("announcement_targets");op.drop_table("announcements")
