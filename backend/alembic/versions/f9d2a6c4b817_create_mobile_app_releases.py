"""create mobile app releases

Revision ID: f9d2a6c4b817
Revises: e5b7c9d1a204
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision:str="f9d2a6c4b817"
down_revision:str|Sequence[str]|None="e5b7c9d1a204"
branch_labels:str|Sequence[str]|None=None
depends_on:str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("mobile_app_releases",sa.Column("platform",sa.String(20),nullable=False),sa.Column("version",sa.String(40),nullable=False),sa.Column("version_code",sa.Integer(),nullable=False),sa.Column("filename",sa.String(255),nullable=False),sa.Column("file_reference",sa.String(255),nullable=False),sa.Column("file_size",sa.Integer(),nullable=False),sa.Column("sha256",sa.String(64),nullable=False),sa.Column("release_notes",sa.Text(),server_default="",nullable=False),sa.Column("status",sa.String(20),server_default="draft",nullable=False),sa.Column("is_latest",sa.Boolean(),server_default=sa.false(),nullable=False),sa.Column("released_at",sa.DateTime(timezone=True),nullable=True),sa.Column("created_by_user_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.CheckConstraint("file_size > 0",name=op.f("ck_mobile_app_releases_mobile_app_release_file_size")),sa.CheckConstraint("platform IN ('android')",name=op.f("ck_mobile_app_releases_mobile_app_release_platform")),sa.CheckConstraint("status IN ('draft','published','retired')",name=op.f("ck_mobile_app_releases_mobile_app_release_status")),sa.CheckConstraint("version_code > 0",name=op.f("ck_mobile_app_releases_mobile_app_release_version_code")),sa.ForeignKeyConstraint(["created_by_user_id"],["users.id"],name=op.f("fk_mobile_app_releases_created_by_user_id_users"),ondelete="RESTRICT"),sa.PrimaryKeyConstraint("id",name=op.f("pk_mobile_app_releases")),sa.UniqueConstraint("file_reference",name=op.f("uq_mobile_app_releases_file_reference")),sa.UniqueConstraint("platform","version",name="uq_mobile_app_releases_platform_version"),sa.UniqueConstraint("platform","version_code",name="uq_mobile_app_releases_platform_version_code"))
    op.create_index(op.f("ix_mobile_app_releases_created_by_user_id"),"mobile_app_releases",["created_by_user_id"])
    op.create_index(op.f("ix_mobile_app_releases_is_latest"),"mobile_app_releases",["is_latest"])
    op.create_index(op.f("ix_mobile_app_releases_platform"),"mobile_app_releases",["platform"])
    op.create_index(op.f("ix_mobile_app_releases_status"),"mobile_app_releases",["status"])
    op.create_index("uq_mobile_app_releases_latest_platform","mobile_app_releases",["platform"],unique=True,postgresql_where=sa.text("is_latest IS TRUE"))
def downgrade()->None:
    op.drop_index("uq_mobile_app_releases_latest_platform",table_name="mobile_app_releases")
    op.drop_index(op.f("ix_mobile_app_releases_status"),table_name="mobile_app_releases")
    op.drop_index(op.f("ix_mobile_app_releases_platform"),table_name="mobile_app_releases")
    op.drop_index(op.f("ix_mobile_app_releases_is_latest"),table_name="mobile_app_releases")
    op.drop_index(op.f("ix_mobile_app_releases_created_by_user_id"),table_name="mobile_app_releases")
    op.drop_table("mobile_app_releases")
