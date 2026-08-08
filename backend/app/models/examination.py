from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, Time, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.examination_score import ExaminationScore
    from app.models.course_offering import CourseOffering
    from app.models.institution import Institution
    from app.models.lecturer_assignment import LecturerAssignment


class Examination(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "examinations"
    __table_args__ = (
        CheckConstraint("examination_type IN ('written', 'practical', 'oral', 'project_defense', 'clinical', 'other')", name="examination_type"),
        CheckConstraint("delivery_mode IN ('physical', 'online', 'hybrid')", name="examination_delivery_mode"),
        CheckConstraint("status IN ('draft', 'scheduled', 'completed', 'cancelled', 'postponed', 'inactive')", name="examination_status"),
        CheckConstraint("maximum_score > 0", name="examination_maximum_score"),
        CheckConstraint("weight_percentage > 0 AND weight_percentage <= 100", name="examination_weight_percentage"),
        CheckConstraint("start_time < end_time", name="examination_times"),
        Index("uq_examinations_offering_normalized_title", "course_offering_id", func.lower(func.btrim(text("title"))), unique=True, postgresql_where=text("status != 'inactive'")),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    course_offering_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="RESTRICT"), nullable=False, index=True)
    lecturer_assignment_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("lecturer_assignments.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    examination_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    maximum_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    weight_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_mode: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="examinations")
    course_offering: Mapped[CourseOffering] = relationship(back_populates="examinations")
    lecturer_assignment: Mapped[LecturerAssignment] = relationship(back_populates="examinations")
    examination_scores: Mapped[list[ExaminationScore]] = relationship(back_populates="examination")
