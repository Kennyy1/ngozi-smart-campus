from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.course_registration import CourseRegistration
    from app.models.institution import Institution
    from app.models.programme import Programme
    from app.models.user import User


class Student(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "matriculation_number",
            name="uq_students_institution_matriculation_number",
        ),
        UniqueConstraint("user_id", name="uq_students_user_id"),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    programme_id: Mapped[UUIDType | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("programmes.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    matriculation_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    admission_year: Mapped[int] = mapped_column(Integer, nullable=False)
    current_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    enrollment_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )
    graduation_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="students")
    user: Mapped[User] = relationship(back_populates="student_profile")
    programme: Mapped[Programme | None] = relationship(back_populates="students")
    course_registrations: Mapped[list[CourseRegistration]] = relationship(
        back_populates="student",
    )
