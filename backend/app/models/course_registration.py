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
    from app.models.assessment_score import AssessmentScore
    from app.models.examination_score import ExaminationScore
    from app.models.attendance_record import AttendanceRecord
    from app.models.course_offering import CourseOffering
    from app.models.institution import Institution
    from app.models.student import Student
    from app.models.result import Result


class CourseRegistration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "course_registrations"
    __table_args__ = (
        CheckConstraint(
            "registration_status IN ('registered', 'dropped')",
            name="course_registration_registration_status",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="course_registration_status",
        ),
        Index(
            "uq_course_registrations_active_student_offering",
            "student_id",
            "course_offering_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    course_offering_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("course_offerings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    registration_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="registered",
        index=True,
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    dropped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")

    institution: Mapped[Institution] = relationship(back_populates="course_registrations")
    student: Mapped[Student] = relationship(back_populates="course_registrations")
    course_offering: Mapped[CourseOffering] = relationship(
        back_populates="course_registrations",
    )
    attendance_records: Mapped[list[AttendanceRecord]] = relationship(back_populates="course_registration")
    assessment_scores: Mapped[list[AssessmentScore]] = relationship(back_populates="course_registration")
    examination_scores: Mapped[list[ExaminationScore]] = relationship(back_populates="course_registration")
    results: Mapped[list[Result]] = relationship(back_populates="course_registration")
