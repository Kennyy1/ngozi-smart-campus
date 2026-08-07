from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assessment_score import AssessmentScore
    from app.models.course_offering import CourseOffering
    from app.models.institution import Institution
    from app.models.lecturer_assignment import LecturerAssignment


class AssessmentComponent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_components"
    __table_args__ = (
        CheckConstraint(
            "assessment_type IN ('attendance', 'quiz', 'assignment', 'test', 'project', "
            "'presentation', 'laboratory', 'practical', 'mid_semester', 'other')",
            name="assessment_component_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'closed', 'cancelled', 'inactive')",
            name="assessment_component_status",
        ),
        CheckConstraint("maximum_score > 0", name="assessment_component_maximum_score"),
        CheckConstraint(
            "weight_percentage > 0 AND weight_percentage <= 100",
            name="assessment_component_weight_percentage",
        ),
        Index(
            "uq_assessment_components_offering_normalized_title",
            "course_offering_id",
            func.lower(func.btrim(text("title"))),
            unique=True,
            postgresql_where=text("status != 'inactive'"),
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    course_offering_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), nullable=False, index=True)
    lecturer_assignment_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("lecturer_assignments.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    maximum_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    weight_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    scheduled_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="assessment_components")
    course_offering: Mapped[CourseOffering] = relationship(back_populates="assessment_components")
    lecturer_assignment: Mapped[LecturerAssignment] = relationship(back_populates="assessment_components")
    assessment_scores: Mapped[list[AssessmentScore]] = relationship(back_populates="assessment_component")
