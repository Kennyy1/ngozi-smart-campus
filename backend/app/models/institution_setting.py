from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.institution import Institution


class InstitutionSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institution_settings"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "setting_key",
            name="uq_institution_settings_institution_setting_key",
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    setting_key: Mapped[str] = mapped_column(String(100), nullable=False)
    setting_value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    value_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    institution: Mapped[Institution] = relationship(back_populates="settings")
