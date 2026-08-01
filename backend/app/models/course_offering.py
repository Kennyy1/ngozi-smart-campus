from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.academic_session import AcademicSession
    from app.models.course import Course
    from app.models.course_registration import CourseRegistration
    from app.models.institution import Institution
    from app.models.semester import Semester


class CourseOffering(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "course_offerings"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "academic_session_id",
            "semester_id",
            name="uq_course_offerings_course_session_semester",
        ),
        CheckConstraint(
            "capacity IS NULL OR capacity > 0",
            name="course_offering_capacity",
        ),
        CheckConstraint(
            "registration_start_date IS NULL OR registration_end_date IS NULL "
            "OR registration_start_date < registration_end_date",
            name="course_offering_registration_window",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="course_offering_status",
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    academic_session_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semester_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("semesters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registration_open: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    registration_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="course_offerings")
    course: Mapped[Course] = relationship(back_populates="course_offerings")
    academic_session: Mapped[AcademicSession] = relationship(back_populates="course_offerings")
    semester: Mapped[Semester] = relationship(back_populates="course_offerings")
    course_registrations: Mapped[list[CourseRegistration]] = relationship(
        back_populates="course_offering",
    )
