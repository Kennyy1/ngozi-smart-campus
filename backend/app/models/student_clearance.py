from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.clearance_requirement import ClearanceRequirement
    from app.models.institution import Institution
    from app.models.student import Student
    from app.models.user import User


class StudentClearance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_clearances"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'cleared', 'rejected', 'waived', 'inactive')", name="student_clearance_status"),
        Index(
            "uq_student_clearances_active_student_requirement",
            "student_id", "clearance_requirement_id",
            unique=True,
            postgresql_where=text("status <> 'inactive'"),
            sqlite_where=text("status <> 'inactive'"),
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="RESTRICT"), nullable=False, index=True)
    clearance_requirement_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("clearance_requirements.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[UUIDType | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="student_clearances")
    student: Mapped[Student] = relationship(back_populates="clearances")
    clearance_requirement: Mapped[ClearanceRequirement] = relationship(back_populates="student_clearances")
    reviewed_by_user: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_user_id])
