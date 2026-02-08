"""Tests for the PromptService."""

from __future__ import annotations

import json

import pytest

from pv.services.prompt_service import PromptService


class TestCreatePrompt:
    def test_create_prompt(self, service: PromptService) -> None:
        prompt = service.create_prompt("my-prompt")
        assert prompt.name == "my-prompt"
        assert prompt.id is not None

    def test_create_duplicate_raises(self, service: PromptService) -> None:
        service.create_prompt("dup")
        with pytest.raises(ValueError, match="already exists"):
            service.create_prompt("dup")


class TestAddVersion:
    def test_add_first_version(self, service: PromptService) -> None:
        ver = service.add_version("test-prompt", "Hello, world!")
        assert ver.version_number == 1
        assert ver.content == "Hello, world!"
        assert len(ver.content_hash) == 64

    def test_add_multiple_versions(self, service: PromptService) -> None:
        service.add_version("p", "v1")
        v2 = service.add_version("p", "v2")
        assert v2.version_number == 2

    def test_add_version_with_tags_and_note(self, service: PromptService) -> None:
        ver = service.add_version("p", "content", tags=["prod", "v1"], note="Initial")
        assert ver.note == "Initial"
        assert {t.name for t in ver.tags} == {"prod", "v1"}

    def test_auto_creates_prompt(self, service: PromptService) -> None:
        ver = service.add_version("new-prompt", "some content")
        assert ver.version_number == 1
        prompt = service.get_prompt("new-prompt")
        assert prompt.name == "new-prompt"


class TestGetVersion:
    def test_get_specific_version(self, service: PromptService) -> None:
        service.add_version("p", "v1-content")
        service.add_version("p", "v2-content")
        ver = service.get_version("p", 1)
        assert ver.content == "v1-content"

    def test_get_latest_version(self, service: PromptService) -> None:
        service.add_version("p", "v1")
        service.add_version("p", "v2-latest")
        latest = service.get_latest_version("p")
        assert latest.content == "v2-latest"

    def test_get_nonexistent_version_raises(self, service: PromptService) -> None:
        service.add_version("p", "v1")
        with pytest.raises(ValueError, match="not found"):
            service.get_version("p", 99)


class TestListVersions:
    def test_list_versions(self, service: PromptService) -> None:
        service.add_version("p", "a")
        service.add_version("p", "b")
        service.add_version("p", "c")
        versions = service.list_versions("p")
        assert len(versions) == 3
        assert [v.version_number for v in versions] == [1, 2, 3]


class TestDiff:
    def test_diff_versions(self, service: PromptService) -> None:
        service.add_version("p", "line1\nline2\n")
        service.add_version("p", "line1\nmodified\n")
        result = service.diff_versions("p", 1, 2)
        assert "-line2" in result
        assert "+modified" in result

    def test_diff_no_changes(self, service: PromptService) -> None:
        service.add_version("p", "same")
        service.add_version("p", "same")
        result = service.diff_versions("p", 1, 2)
        assert result == ""


class TestRollback:
    def test_rollback_creates_new_version(self, service: PromptService) -> None:
        service.add_version("p", "v1-content", tags=["original"])
        service.add_version("p", "v2-content")
        new_ver = service.rollback("p", 1)
        assert new_ver.version_number == 3
        assert new_ver.content == "v1-content"
        assert "Rollback" in (new_ver.note or "")


class TestExport:
    def test_export_json(self, service: PromptService) -> None:
        service.add_version("p", "content-v1", tags=["t1"], note="first")
        service.add_version("p", "content-v2")
        result = json.loads(service.export_prompt("p"))
        assert result["name"] == "p"
        assert len(result["versions"]) == 2
        assert result["versions"][0]["tags"] == ["t1"]

    def test_export_to_file(self, service: PromptService, tmp_path) -> None:
        service.add_version("p", "content")
        path = tmp_path / "export.json"
        service.export_to_file("p", path)
        data = json.loads(path.read_text())
        assert data["name"] == "p"


class TestTagManagement:
    def test_add_tag(self, service: PromptService) -> None:
        service.add_version("p", "v1")
        service.add_tag("p", 1, "deployed")
        ver = service.get_version("p", 1)
        assert "deployed" in [t.name for t in ver.tags]

    def test_remove_tag(self, service: PromptService) -> None:
        service.add_version("p", "v1", tags=["remove-me"])
        service.remove_tag("p", 1, "remove-me")
        ver = service.get_version("p", 1)
        assert "remove-me" not in [t.name for t in ver.tags]


class TestDeletePrompt:
    def test_delete_prompt(self, service: PromptService) -> None:
        service.add_version("p", "v1")
        service.delete_prompt("p")
        with pytest.raises(ValueError, match="not found"):
            service.get_prompt("p")

    def test_delete_nonexistent_raises(self, service: PromptService) -> None:
        with pytest.raises(ValueError, match="not found"):
            service.delete_prompt("nope")


class TestListPrompts:
    def test_list_empty(self, service: PromptService) -> None:
        assert service.list_prompts() == []

    def test_list_multiple(self, service: PromptService) -> None:
        service.add_version("alpha", "a")
        service.add_version("beta", "b")
        names = [p.name for p in service.list_prompts()]
        assert names == ["alpha", "beta"]
