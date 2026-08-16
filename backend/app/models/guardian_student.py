from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, false, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.guardian import Guardian
    from app.models.institution import Institution
    from app.models.student import Student


class GuardianStudent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "guardian_students"
    __table_args__ = (
        CheckConstraint("relationship_type IN ('father','mother','guardian','sponsor','other')", name="guardian_student_relationship_type"),
        CheckConstraint("status IN ('pending','verified','suspended','revoked')", name="guardian_student_status"),
        Index(
            "uq_guardian_students_active_pair",
            "guardian_id",
            "student_id",
            unique=True,
            postgresql_where=text("status <> 'revoked'"),
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    guardian_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("guardians.id", ondelete="RESTRICT"), nullable=False, index=True)
    student_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending", index=True)
    can_view_results: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    can_view_attendance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    can_view_academic_performance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    can_view_transcript: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    can_view_clearance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())

    institution: Mapped[Institution] = relationship(back_populates="guardian_student_relationships")
    guardian: Mapped[Guardian] = relationship(back_populates="student_relationships")
    student: Mapped[Student] = relationship(back_populates="guardian_relationships")
