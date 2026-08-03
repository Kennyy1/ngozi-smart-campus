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
    from app.models.class_session import ClassSession
    from app.models.course_registration import CourseRegistration
    from app.models.institution import Institution
    from app.models.user import User


class AttendanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        CheckConstraint(
            "attendance_status IN ('present', 'absent', 'late', 'excused')",
            name="attendance_record_attendance_status",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="attendance_record_status",
        ),
        CheckConstraint(
            "(attendance_status = 'late' AND check_in_time IS NOT NULL) OR "
            "(attendance_status IN ('absent', 'excused') AND check_in_time IS NULL) OR "
            "attendance_status = 'present'",
            name="attendance_record_check_in_state",
        ),
        Index(
            "uq_attendance_records_active_session_registration",
            "class_session_id",
            "course_registration_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_session_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_sessions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    course_registration_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("course_registrations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    attendance_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    check_in_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by_user_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)

    institution: Mapped[Institution] = relationship(back_populates="attendance_records")
    class_session: Mapped[ClassSession] = relationship(back_populates="attendance_records")
    course_registration: Mapped[CourseRegistration] = relationship(back_populates="attendance_records")
    recorded_by_user: Mapped[User] = relationship(back_populates="recorded_attendance_records")
