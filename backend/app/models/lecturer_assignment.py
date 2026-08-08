from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assessment_component import AssessmentComponent
    from app.models.class_session import ClassSession
    from app.models.course_offering import CourseOffering
    from app.models.institution import Institution
    from app.models.lecturer import Lecturer
    from app.models.examination import Examination


class LecturerAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lecturer_assignments"
    __table_args__ = (
        CheckConstraint("assignment_role IN ('primary', 'co_instructor', 'teaching_assistant', 'lab_instructor')", name="lecturer_assignment_role"),
        CheckConstraint("status IN ('active', 'inactive')", name="lecturer_assignment_status"),
        CheckConstraint("ended_at IS NULL OR assigned_at < ended_at", name="lecturer_assignment_dates"),
        CheckConstraint("(assignment_role = 'primary' AND is_primary) OR (assignment_role != 'primary' AND NOT is_primary)", name="lecturer_assignment_primary_role"),
        Index("uq_lecturer_assignments_active_lecturer_offering", "lecturer_id", "course_offering_id", unique=True, postgresql_where=text("status = 'active'")),
        Index("uq_lecturer_assignments_active_primary_offering", "course_offering_id", unique=True, postgresql_where=text("status = 'active' AND is_primary")),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    lecturer_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("lecturers.id", ondelete="RESTRICT"), nullable=False, index=True)
    course_offering_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), nullable=False, index=True)
    assignment_role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="lecturer_assignments")
    lecturer: Mapped[Lecturer] = relationship(back_populates="lecturer_assignments")
    course_offering: Mapped[CourseOffering] = relationship(back_populates="lecturer_assignments")
    class_sessions: Mapped[list[ClassSession]] = relationship(back_populates="lecturer_assignment")
    assessment_components: Mapped[list[AssessmentComponent]] = relationship(back_populates="lecturer_assignment")
    examinations: Mapped[list[Examination]] = relationship(back_populates="lecturer_assignment")
