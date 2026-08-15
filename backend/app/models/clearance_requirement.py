from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.student_clearance import StudentClearance


class ClearanceRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clearance_requirements"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_clearance_requirements_institution_code"),
        CheckConstraint("sequence_number > 0", name="clearance_requirement_sequence_number"),
        CheckConstraint("status IN ('active', 'inactive')", name="clearance_requirement_status"),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)

    institution: Mapped[Institution] = relationship(back_populates="clearance_requirements")
    student_clearances: Mapped[list[StudentClearance]] = relationship(back_populates="clearance_requirement")
