"""Core business-logic service for prompts and versions."""

from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pv.models.prompt import Prompt, PromptVersion, Tag


class PromptService:
    """Service layer wrapping all prompt operations."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Prompt CRUD
    # ------------------------------------------------------------------

    def create_prompt(self, name: str) -> Prompt:
        """Create a new prompt by name. Raises ValueError if it exists."""
        existing = self._session.execute(
            select(Prompt).where(Prompt.name == name)
        ).scalar_one_or_none()
        if existing is not None:
            raise ValueError(f"Prompt '{name}' already exists.")
        prompt = Prompt(name=name)
        self._session.add(prompt)
        self._session.flush()
        return prompt

    def get_prompt(self, name: str) -> Prompt:
        """Fetch a prompt by name. Raises ValueError if not found."""
        prompt = self._session.execute(
            select(Prompt).where(Prompt.name == name)
        ).scalar_one_or_none()
        if prompt is None:
            raise ValueError(f"Prompt '{name}' not found.")
        return prompt

    def list_prompts(self) -> list[Prompt]:
        """Return all prompts ordered by name."""
        return list(self._session.execute(select(Prompt).order_by(Prompt.name)).scalars().all())

    def delete_prompt(self, name: str) -> None:
        """Delete a prompt and all its versions."""
        prompt = self.get_prompt(name)
        self._session.delete(prompt)
        self._session.flush()

    # ------------------------------------------------------------------
    # Version CRUD
    # ------------------------------------------------------------------

    @staticmethod
    def _content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _get_or_create_tag(self, tag_name: str) -> Tag:
        with self._session.no_autoflush:
            tag = self._session.execute(
                select(Tag).where(Tag.name == tag_name)
            ).scalar_one_or_none()
        if tag is None:
            tag = Tag(name=tag_name)
            self._session.add(tag)
            self._session.flush()
        return tag

    def add_version(
        self,
        prompt_name: str,
        content: str,
        tags: list[str] | None = None,
        note: str | None = None,
    ) -> PromptVersion:
        """Add a new version to a prompt, creating the prompt if needed."""
        try:
            prompt = self.get_prompt(prompt_name)
        except ValueError:
            prompt = self.create_prompt(prompt_name)

        # Determine next version number
        max_ver = max((v.version_number for v in prompt.versions), default=0)
        version_number = max_ver + 1

        version = PromptVersion(
            prompt_id=prompt.id,
            version_number=version_number,
            content=content,
            content_hash=self._content_hash(content),
            note=note,
        )
        self._session.add(version)
        if tags:
            for tag_name in tags:
                version.tags.append(self._get_or_create_tag(tag_name))

        self._session.flush()
        return version

    def get_version(self, prompt_name: str, version_number: int) -> PromptVersion:
        """Fetch a specific version of a prompt."""
        prompt = self.get_prompt(prompt_name)
        version = self._session.execute(
            select(PromptVersion)
            .options(selectinload(PromptVersion.tags))
            .where(
                PromptVersion.prompt_id == prompt.id,
                PromptVersion.version_number == version_number,
            )
        ).scalar_one_or_none()
        if version is None:
            raise ValueError(f"Version {version_number} not found for prompt '{prompt_name}'.")
        return version

    def get_latest_version(self, prompt_name: str) -> PromptVersion:
        """Fetch the latest version of a prompt."""
        prompt = self.get_prompt(prompt_name)
        version = (
            self._session.execute(
                select(PromptVersion)
                .options(selectinload(PromptVersion.tags))
                .where(PromptVersion.prompt_id == prompt.id)
                .order_by(PromptVersion.version_number.desc())
            )
            .scalars()
            .first()
        )
        if version is None:
            raise ValueError(f"No versions found for prompt '{prompt_name}'.")
        return version

    def list_versions(self, prompt_name: str) -> list[PromptVersion]:
        """List all versions of a prompt."""
        prompt = self.get_prompt(prompt_name)
        return list(
            self._session.execute(
                select(PromptVersion)
                .options(selectinload(PromptVersion.tags))
                .where(PromptVersion.prompt_id == prompt.id)
                .order_by(PromptVersion.version_number)
            )
            .scalars()
            .all()
        )

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff_versions(
        self,
        prompt_name: str,
        v1: int,
        v2: int,
    ) -> str:
        """Return a unified diff between two versions of a prompt."""
        ver1 = self.get_version(prompt_name, v1)
        ver2 = self.get_version(prompt_name, v2)
        lines1 = ver1.content.splitlines(keepends=True)
        lines2 = ver2.content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            lines1,
            lines2,
            fromfile=f"{prompt_name} v{v1}",
            tofile=f"{prompt_name} v{v2}",
        )
        return "".join(diff)

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback(self, prompt_name: str, to_version: int) -> PromptVersion:
        """Rollback a prompt to a previous version by copying it as a new version."""
        old = self.get_version(prompt_name, to_version)
        tag_names = [t.name for t in old.tags]
        note = f"Rollback to v{to_version}"
        return self.add_version(prompt_name, old.content, tags=tag_names, note=note)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_prompt(self, prompt_name: str) -> str:
        """Export all versions of a prompt as JSON."""
        prompt = self.get_prompt(prompt_name)
        versions = self.list_versions(prompt_name)
        data = {
            "name": prompt.name,
            "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
            "versions": [
                {
                    "version_number": v.version_number,
                    "content": v.content,
                    "content_hash": v.content_hash,
                    "note": v.note,
                    "tags": [t.name for t in v.tags],
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                }
                for v in versions
            ],
        }
        return json.dumps(data, indent=2)

    def export_to_file(self, prompt_name: str, path: Path) -> Path:
        """Export prompt JSON to a file."""
        data = self.export_prompt(prompt_name)
        path.write_text(data, encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # Tag management
    # ------------------------------------------------------------------

    def add_tag(self, prompt_name: str, version_number: int, tag_name: str) -> None:
        """Add a tag to a specific version."""
        version = self.get_version(prompt_name, version_number)
        tag = self._get_or_create_tag(tag_name)
        if tag not in version.tags:
            version.tags.append(tag)
            self._session.flush()

    def remove_tag(self, prompt_name: str, version_number: int, tag_name: str) -> None:
        """Remove a tag from a specific version."""
        version = self.get_version(prompt_name, version_number)
        tag = self._session.execute(select(Tag).where(Tag.name == tag_name)).scalar_one_or_none()
        if tag is None:
            raise ValueError(f"Tag '{tag_name}' not found.")
        if tag in version.tags:
            version.tags.remove(tag)
            self._session.flush()
