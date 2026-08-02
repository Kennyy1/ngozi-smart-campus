from __future__ import annotations

from datetime import date, time
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text, Time, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.course_offering import CourseOffering
    from app.models.institution import Institution
    from app.models.lecturer_assignment import LecturerAssignment


class ClassSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "class_sessions"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="class_session_time_range"),
        CheckConstraint("session_type IN ('lecture', 'tutorial', 'laboratory', 'practical', 'seminar')", name="class_session_type"),
        CheckConstraint("delivery_mode IN ('physical', 'online', 'hybrid')", name="class_session_delivery_mode"),
        CheckConstraint("status IN ('scheduled', 'completed', 'cancelled', 'postponed', 'inactive')", name="class_session_status"),
        Index("uq_class_sessions_active_exact_slot", "course_offering_id", "session_date", "start_time", "end_time", unique=True, postgresql_where=text("status IN ('scheduled', 'completed')")),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    course_offering_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), nullable=False, index=True)
    lecturer_assignment_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("lecturer_assignments.id", ondelete="RESTRICT"), nullable=False, index=True)
    session_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    session_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="physical", index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="scheduled", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="class_sessions")
    course_offering: Mapped[CourseOffering] = relationship(back_populates="class_sessions")
    lecturer_assignment: Mapped[LecturerAssignment] = relationship(back_populates="class_sessions")
