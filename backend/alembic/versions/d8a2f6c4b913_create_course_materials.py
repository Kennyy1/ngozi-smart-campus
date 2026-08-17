"""Create course materials.

Revision ID: d8a2f6c4b913
Revises: c1f4a8d2e607
"""
from alembic import op
import sqlalchemy as sa

revision="d8a2f6c4b913";down_revision="c1f4a8d2e607";branch_labels=None;depends_on=None

def upgrade():
    op.create_table("course_materials",
        sa.Column("institution_id",sa.UUID(),nullable=False),sa.Column("course_offering_id",sa.UUID(),nullable=False),sa.Column("uploaded_by_user_id",sa.UUID(),nullable=False),
        sa.Column("title",sa.String(255),nullable=False),sa.Column("description",sa.Text(),nullable=True),sa.Column("material_type",sa.String(40),nullable=False),sa.Column("file_reference",sa.String(500),nullable=True),sa.Column("external_url",sa.String(2048),nullable=True),sa.Column("is_published",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("published_at",sa.DateTime(timezone=True),nullable=True),
        sa.Column("id",sa.UUID(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.CheckConstraint("material_type IN ('lecture_note','slide','assignment_resource','reading','link','other')",name=op.f("ck_course_materials_course_material_type")),sa.CheckConstraint("external_url IS NOT NULL OR file_reference IS NOT NULL",name=op.f("ck_course_materials_course_material_reference")),
        sa.ForeignKeyConstraint(["institution_id"],["institutions.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["course_offering_id"],["course_offerings.id"],ondelete="CASCADE"),sa.ForeignKeyConstraint(["uploaded_by_user_id"],["users.id"],ondelete="RESTRICT"),sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("course_offering_id","title",name="uq_course_materials_offering_title"))
    for c in ("institution_id","course_offering_id","uploaded_by_user_id","is_published"):op.create_index(op.f(f"ix_course_materials_{c}"),"course_materials",[c])

def downgrade():
    for c in reversed(("institution_id","course_offering_id","uploaded_by_user_id","is_published")):op.drop_index(op.f(f"ix_course_materials_{c}"),table_name="course_materials")
    op.drop_table("course_materials")
