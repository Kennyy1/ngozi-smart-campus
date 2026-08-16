"""Create institution-scoped guardian portal relationships.

Revision ID: c1f4a8d2e607
Revises: b7e3c9a1d524
Create Date: 2026-08-16
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str="c1f4a8d2e607"
down_revision: str|Sequence[str]|None="b7e3c9a1d524"
branch_labels=None
depends_on=None

def upgrade()->None:
    op.create_table("guardians",
        sa.Column("institution_id",sa.UUID(),nullable=False),sa.Column("user_id",sa.UUID(),nullable=False),
        sa.Column("occupation",sa.String(255),nullable=True),sa.Column("address",sa.Text(),nullable=True),sa.Column("emergency_contact",sa.String(255),nullable=True),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column("id",sa.UUID(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.ForeignKeyConstraint(["institution_id"],["institutions.id"],name=op.f("fk_guardians_institution_id_institutions"),ondelete="CASCADE"),sa.ForeignKeyConstraint(["user_id"],["users.id"],name=op.f("fk_guardians_user_id_users"),ondelete="CASCADE"),sa.PrimaryKeyConstraint("id",name=op.f("pk_guardians")),sa.UniqueConstraint("user_id",name="uq_guardians_user_id"))
    for c in ("institution_id","user_id","is_active"):op.create_index(op.f(f"ix_guardians_{c}"),"guardians",[c])
    op.create_table("guardian_students",
        sa.Column("institution_id",sa.UUID(),nullable=False),sa.Column("guardian_id",sa.UUID(),nullable=False),sa.Column("student_id",sa.UUID(),nullable=False),sa.Column("relationship_type",sa.String(30),nullable=False),sa.Column("is_primary",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("status",sa.String(30),nullable=False,server_default="pending"),
        sa.Column("can_view_results",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("can_view_attendance",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("can_view_academic_performance",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("can_view_transcript",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("can_view_clearance",sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column("id",sa.UUID(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),
        sa.CheckConstraint("relationship_type IN ('father','mother','guardian','sponsor','other')",name=op.f("ck_guardian_students_guardian_student_relationship_type")),sa.CheckConstraint("status IN ('pending','verified','suspended','revoked')",name=op.f("ck_guardian_students_guardian_student_status")),
        sa.ForeignKeyConstraint(["institution_id"],["institutions.id"],name=op.f("fk_guardian_students_institution_id_institutions"),ondelete="CASCADE"),sa.ForeignKeyConstraint(["guardian_id"],["guardians.id"],name=op.f("fk_guardian_students_guardian_id_guardians"),ondelete="RESTRICT"),sa.ForeignKeyConstraint(["student_id"],["students.id"],name=op.f("fk_guardian_students_student_id_students"),ondelete="RESTRICT"),sa.PrimaryKeyConstraint("id",name=op.f("pk_guardian_students")))
    for c in ("institution_id","guardian_id","student_id","status"):op.create_index(op.f(f"ix_guardian_students_{c}"),"guardian_students",[c])
    op.create_index("uq_guardian_students_active_pair","guardian_students",["guardian_id","student_id"],unique=True,postgresql_where=sa.text("status <> 'revoked'"))

def downgrade()->None:
    op.drop_index("uq_guardian_students_active_pair",table_name="guardian_students")
    for c in reversed(("institution_id","guardian_id","student_id","status")):op.drop_index(op.f(f"ix_guardian_students_{c}"),table_name="guardian_students")
    op.drop_table("guardian_students")
    for c in reversed(("institution_id","user_id","is_active")):op.drop_index(op.f(f"ix_guardians_{c}"),table_name="guardians")
    op.drop_table("guardians")
