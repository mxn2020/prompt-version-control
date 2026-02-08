from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field


class PromptCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Unique prompt name")


class PromptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime.datetime
    version_count: int = 0
    latest_version: int | None = None


class PromptVersionCreate(BaseModel):
    content: str = Field(..., min_length=1, description="Prompt content text")
    tags: list[str] = Field(default_factory=list, description="Optional tags")
    note: str | None = Field(default=None, description="Optional note for this version")


class PromptVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_number: int
    content: str
    content_hash: str
    note: str | None
    created_at: datetime.datetime
    tags: list[str] = Field(default_factory=list)
