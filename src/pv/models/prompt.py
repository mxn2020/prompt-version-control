from __future__ import annotations

import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pv.models.base import Base

prompt_version_tags = Table(
    "prompt_version_tags",
    Base.metadata,
    Column(
        "version_id",
        Integer,
        ForeignKey("prompt_versions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    versions: Mapped[list[PromptVersion]] = relationship(
        "PromptVersion",
        back_populates="prompt",
        cascade="all, delete-orphan",
        order_by="PromptVersion.version_number",
    )

    def __repr__(self) -> str:
        return f"<Prompt(name={self.name!r})>"


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prompt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    prompt: Mapped[Prompt] = relationship("Prompt", back_populates="versions")
    tags: Mapped[list[Tag]] = relationship(
        "Tag",
        secondary=prompt_version_tags,
        back_populates="versions",
        overlaps="versions",
    )

    def __repr__(self) -> str:
        return f"<PromptVersion(prompt_id={self.prompt_id}, v={self.version_number})>"


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    versions: Mapped[list[PromptVersion]] = relationship(
        "PromptVersion",
        secondary=prompt_version_tags,
        back_populates="tags",
        overlaps="tags",
    )

    def __repr__(self) -> str:
        return f"<Tag(name={self.name!r})>"
