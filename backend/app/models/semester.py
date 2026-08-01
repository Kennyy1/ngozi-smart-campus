from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.academic_session import AcademicSession
    from app.models.course_offering import CourseOffering
    from app.models.institution import Institution


class Semester(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "semesters"
    __table_args__ = (
        UniqueConstraint("academic_session_id", "name", name="uq_semesters_academic_session_name"),
        UniqueConstraint("academic_session_id", "sequence_number", name="uq_semesters_academic_session_sequence"),
        CheckConstraint("start_date < end_date", name="semester_date_range"),
        CheckConstraint("sequence_number > 0", name="semester_sequence_number"),
        CheckConstraint("status IN ('active', 'inactive')", name="semester_status"),
        Index("uq_semesters_current_institution", "institution_id", unique=True, postgresql_where=text("is_current")),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    academic_session_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="semesters")
    academic_session: Mapped[AcademicSession] = relationship(back_populates="semesters")
    course_offerings: Mapped[list[CourseOffering]] = relationship(
        back_populates="semester",
    )
