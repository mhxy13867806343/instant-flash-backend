from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AdminAgreement(TimestampMixin, Base):
    __tablename__ = "admin_agreements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
