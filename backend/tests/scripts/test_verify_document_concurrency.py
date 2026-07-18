"""Auditable document concurrency verification script tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import httpx
import pytest


SCRIPT_PATH = Path(__file__).parents[3] / "scripts" / "verify_document_concurrency.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("verify_document_concurrency", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_samples_are_structurally_valid_and_extract_nonempty(tmp_path):
    module = _load_script()
    samples = module.generate_samples(tmp_path, scale=1)

    assert set(samples) == {"pdf", "docx", "xlsx", "txt"}
    validations = module.validate_generated_samples(samples)
    assert all(item["official_reopen"] for item in validations.values())
    assert all(item["extracted_char_count"] > 0 for item in validations.values())
    assert validations["pdf"]["page_count"] >= 2
    assert validations["xlsx"]["sheet_count"] >= 2


def test_summary_is_recomputed_from_raw_samples():
    module = _load_script()
    report = {
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:05Z",
        "total_duration_seconds": 5.0,
        "formats": {
            kind: {"status": "completed", "duration_seconds": 1.0, "document_count": 1}
            for kind in ("pdf", "docx", "xlsx", "txt")
        },
        "probes": {
            "health": [
                {"format": "pdf", "duration_seconds": value, "status_code": 200, "error": None}
                for value in (0.1, 0.2, 0.3, 0.4)
            ],
            "projects": [
                {"format": "pdf", "duration_seconds": value, "status_code": 200, "error": None}
                for value in (0.5, 1.0, 1.5, 2.0)
            ],
        },
    }

    summary = module.build_summary(report)
    assert summary["health"] == {
        "samples": 4,
        "failures": 0,
        "p50_seconds": 0.25,
        "p95_seconds": 0.4,
        "max_seconds": 0.4,
    }
    assert summary["projects"]["samples"] == 4
    assert summary["projects"]["p95_seconds"] == 2.0
    markdown = module.render_markdown(report, summary)
    assert "| health | 4 | 0 | 0.250 | 0.400 | 0.400 |" in markdown
    assert "| pdf | completed | 1 | 1.000 |" in markdown


def test_validation_fails_closed_for_counts_http_errors_and_thresholds():
    module = _load_script()
    report = {
        "formats": {
            "pdf": {"status": "failed", "document_count": 0, "cleanup_status": "failed"}
        },
        "probes": {
            "health": [
                {"format": "pdf", "duration_seconds": 2.1, "status_code": 503, "error": "bad"}
            ],
            "projects": [],
        },
    }
    errors = module.validate_report(report)
    assert any("pdf" in error and "failed" in error for error in errors)
    assert any("health" in error and "20" in error for error in errors)
    assert any("projects" in error and "10" in error for error in errors)
    assert any("non-2xx" in error for error in errors)
    assert any("max" in error for error in errors)


def test_main_requires_real_base_url_and_token(monkeypatch):
    module = _load_script()
    monkeypatch.delenv("DOCUMENT_VERIFY_BASE_URL", raising=False)
    monkeypatch.delenv("DOCUMENT_VERIFY_TOKEN", raising=False)
    assert module.main([]) != 0


@pytest.mark.asyncio
async def test_probe_samples_survive_poll_failure(monkeypatch, tmp_path):
    module = _load_script()
    sample = tmp_path / "sample.txt"
    sample.write_text("content", encoding="utf-8")

    class Response:
        status_code = 200
        text = ""

        def __init__(self, payload=None):
            self.payload = payload or {"data": {"id": 7}}

        def json(self):
            return self.payload

    class Client:
        def __init__(self):
            self.deleted = False

        async def post(self, *_args, **_kwargs):
            return Response()

        async def get(self, *_args, **_kwargs):
            data = [] if self.deleted else [{"id": 7, "name": self.name, "status": "failed"}]
            return Response({"data": data})

        async def delete(self, *_args, **_kwargs):
            self.deleted = True
            return Response()

    async def failing_poll(*_args, **_kwargs):
        raise TimeoutError("parse timed out")

    async def successful_probe(_client, _path, kind, name):
        return {
            "format": kind,
            "probe": name,
            "duration_seconds": 0.01,
            "status_code": 200,
            "error": None,
        }

    monkeypatch.setattr(module, "_poll_completion", failing_poll)
    monkeypatch.setattr(module, "_probe", successful_probe)
    probes = {"health": [], "projects": []}

    client = Client()
    original_post = client.post

    async def remembering_post(path, **kwargs):
        if path == "/api/v1/knowledge/upload":
            client.name = kwargs["data"]["name"]
        return await original_post(path, **kwargs)

    client.post = remembering_post
    result = await module._run_format(client, "txt", sample, 0.1, probes)

    assert result["status"] == "failed"
    assert result["cleanup_status"] == "completed"
    assert len(probes["health"]) == module.HEALTH_SAMPLES_PER_FORMAT
    assert len(probes["projects"]) == module.PROJECT_SAMPLES_PER_FORMAT


@pytest.mark.asyncio
async def test_upload_timeout_discovers_and_deletes_owned_orphan(tmp_path):
    module = _load_script()
    sample = tmp_path / "sample.txt"
    sample.write_text("content", encoding="utf-8")

    class Response:
        status_code = 200
        text = ""

        def __init__(self, payload=None):
            self.payload = payload or {"data": {}}

        def json(self):
            return self.payload

    class Client:
        def __init__(self):
            self.upload_name = None
            self.deleted = []

        async def post(self, path, **kwargs):
            if path == "/api/v1/knowledge/upload":
                self.upload_name = kwargs["data"]["name"]
                raise httpx.ReadTimeout("upload response timed out")
            assert path.endswith("/stop")
            return Response()

        async def get(self, path, **_kwargs):
            assert path == "/api/v1/knowledge"
            items = [] if self.deleted else [
                {"id": 41, "name": self.upload_name, "status": "processing"}
            ]
            return Response({"data": items})

        async def delete(self, path, **_kwargs):
            self.deleted.append(int(path.rsplit("/", 1)[1]))
            return Response()

    client = Client()
    result = await module._run_format(
        client,
        "txt",
        sample,
        0.1,
        {"health": [], "projects": []},
    )

    assert client.upload_name.startswith("document-concurrency-txt-")
    assert client.deleted == [41]
    assert result["cleanup_status"] == "completed"
    assert result["cleaned_knowledge_base_ids"] == [41]
