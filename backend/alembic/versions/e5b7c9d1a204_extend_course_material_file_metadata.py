"""Extend Course Materials with uploaded file metadata.

Revision ID: e5b7c9d1a204
Revises: d8a2f6c4b913
"""
from alembic import op
import sqlalchemy as sa
revision="e5b7c9d1a204";down_revision="d8a2f6c4b913";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("course_materials",sa.Column("source_type",sa.String(30),nullable=False,server_default="external_url"))
    op.add_column("course_materials",sa.Column("original_filename",sa.String(255),nullable=True))
    op.add_column("course_materials",sa.Column("mime_type",sa.String(150),nullable=True))
    op.add_column("course_materials",sa.Column("file_size",sa.Integer(),nullable=True))
    op.create_check_constraint(op.f("ck_course_materials_course_material_source_type"),"course_materials","source_type IN ('external_url','uploaded_file')")
    op.create_index(op.f("ix_course_materials_source_type"),"course_materials",["source_type"])
def downgrade():
    op.drop_index(op.f("ix_course_materials_source_type"),table_name="course_materials")
    op.drop_constraint(op.f("ck_course_materials_course_material_source_type"),"course_materials",type_="check")
    for column in ("file_size","mime_type","original_filename","source_type"):op.drop_column("course_materials",column)
