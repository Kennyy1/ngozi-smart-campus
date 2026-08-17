from datetime import datetime
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, false
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CourseMaterial(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "course_materials"
    __table_args__ = (
        UniqueConstraint("course_offering_id", "title", name="uq_course_materials_offering_title"),
        CheckConstraint(
            "material_type IN ('lecture_note','slide','assignment_resource','reading','link','other')",
            name="course_material_type",
        ),
        CheckConstraint("external_url IS NOT NULL OR file_reference IS NOT NULL", name="course_material_reference"),
        CheckConstraint("source_type IN ('external_url','uploaded_file')", name="course_material_source_type"),
    )

    institution_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    course_offering_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by_user_id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_type: Mapped[str] = mapped_column(String(40), nullable=False)
    file_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="external_url", server_default="external_url", index=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false(), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
