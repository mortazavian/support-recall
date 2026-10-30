from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.retrieval.embeddings import EmbeddingError
from app.settings import Settings

JSON_RECORD = {
    "conversation_id": "support-401",
    "date": "2026-10-20",
    "product": "حساب کاربری",
    "category": "ورود",
    "question": "چطور رمز عبور را تغییر بدهم؟",
    "answer": "از تنظیمات حساب گزینه تغییر رمز را انتخاب کنید.",
}
CSV_CONTENT = (
    "شناسه گفت‌وگو,تاریخ,پرسش مشتری,پاسخ پشتیبانی\n"
    "support-402,2026-10-21,کد ورود نمی‌رسد,شماره ثبت‌شده را بررسی کنید.\n"
).encode("utf-8")
CSV_MAPPING = json.dumps(
    {
        "conversation_id": "شناسه گفت‌وگو",
        "date": "تاریخ",
        "question": "پرسش مشتری",
        "answer": "پاسخ پشتیبانی",
    },
    ensure_ascii=False,
)


def _settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path / "data")


class _MemoryVectorIndex:
    def __init__(self) -> None:
        self.fail_index = False
        self.fail_delete = False
        self.status_during_index: str | None = None
        self.sources: set[str] = set()

    def index_source(self, database_path: Path, source_id: str) -> int:
        with sqlite3.connect(database_path) as connection:
            row = connection.execute(
                "SELECT status FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
        self.status_during_index = row[0]
        if self.fail_index:
            raise EmbeddingError("embedding_unavailable", "provider unavailable")
        self.sources.add(source_id)
        return 1

    def delete_source(self, source_id: str) -> None:
        if self.fail_delete:
            raise RuntimeError("simulated vector store failure")
        self.sources.discard(source_id)

    def has_source(self, source_id: str) -> bool:
        return source_id in self.sources


def _create_app(settings: Settings, vector_index: _MemoryVectorIndex | None = None):
    return create_app(settings, vector_index=vector_index or _MemoryVectorIndex())


def _upload(filename: str, content: bytes, content_type: str = "application/octet-stream"):
    return {"file": (filename, content, content_type)}


def _json_upload(filename: str = "support.json"):
    content = json.dumps([JSON_RECORD], ensure_ascii=False).encode("utf-8")
    return _upload(filename, content, "application/json")


def _import_json(client: TestClient, filename: str = "support.json") -> dict:
    response = client.post("/api/sources/import", files=_json_upload(filename))
    assert response.status_code == 200, response.text
    return response.json()


def test_stage1_database_is_additively_migrated_for_sources(tmp_path) -> None:
    settings = _settings(tmp_path)
    settings.data_dir.mkdir(parents=True)
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute(
            "CREATE TABLE app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO app_meta (key, value) VALUES (?, ?)", ("schema_version", "1")
        )

    with sqlite3.connect(settings.database_path) as connection:
        before = connection.execute(
            "SELECT value FROM app_meta WHERE key = ?", ("schema_version",)
        ).fetchone()
    assert before == ("1",)

    with TestClient(_create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200

    with sqlite3.connect(settings.database_path) as connection:
        after = connection.execute(
            "SELECT value FROM app_meta WHERE key = ?", ("schema_version",)
        ).fetchone()
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

    assert after == ("2",)
    assert {"sources", "support_records"} <= tables


def test_upgrade_marks_sources_without_vectors_retryable_without_ollama(tmp_path) -> None:
    settings = _settings(tmp_path)
    vector_index = _MemoryVectorIndex()
    with TestClient(_create_app(settings, vector_index)) as client:
        imported = _import_json(client)
        source_id = imported["source"]["id"]

    vector_index.sources.clear()
    with TestClient(_create_app(settings, vector_index)) as client:
        health = client.get("/api/health")
        source = client.get(f"/api/sources/{source_id}").json()["source"]

        assert health.status_code == 200
        assert source["status"] == "failed"
        assert source["error_code"] == "index_missing"
        assert source["retryable"] is True

        retried = client.post(f"/api/sources/{source_id}/retry")

    assert retried.status_code == 200
    assert retried.json()["source"]["status"] == "ready"


def test_preview_returns_csv_headers_and_never_persists_a_source(tmp_path) -> None:
    settings = _settings(tmp_path)
    with TestClient(_create_app(settings)) as client:
        unmapped = client.post("/api/sources/preview", files=_upload("support.csv", CSV_CONTENT))
        mapped = client.post(
            "/api/sources/preview",
            files=_upload("support.csv", CSV_CONTENT),
            data={"mapping_json": CSV_MAPPING},
        )
        sources = client.get("/api/sources")

    assert unmapped.status_code == 200
    assert unmapped.json() == {
        "format": "csv",
        "columns": ["شناسه گفت‌وگو", "تاریخ", "پرسش مشتری", "پاسخ پشتیبانی"],
        "needs_mapping": True,
        "record_count": None,
        "records": [],
    }
    assert mapped.status_code == 200
    assert mapped.json()["record_count"] == 1
    assert mapped.json()["records"][0]["messages"][0]["content"] == "کد ورود نمی‌رسد"
    assert sources.json() == []


def test_import_persists_records_and_duplicate_content_is_idempotent(tmp_path) -> None:
    with TestClient(_create_app(_settings(tmp_path))) as client:
        imported = _import_json(client)
        source_id = imported["source"]["id"]
        details = client.get(f"/api/sources/{source_id}")
        listed = client.get("/api/sources")
        duplicate = _import_json(client, "renamed-copy.json")

    assert imported["duplicate"] is False
    assert imported["source"]["status"] == "ready"
    assert imported["source"]["record_count"] == 1
    assert details.status_code == 200
    assert details.json()["records"][0]["messages"] == [
        {"role": "customer", "content": JSON_RECORD["question"]},
        {"role": "support", "content": JSON_RECORD["answer"]},
    ]
    assert len(listed.json()) == 1
    assert duplicate["duplicate"] is True
    assert duplicate["source"]["id"] == source_id


def test_preview_returns_persian_validation_error_without_importing(tmp_path) -> None:
    invalid = json.dumps([{"conversation_id": "missing-answer", "question": "پرسش"}]).encode()
    with TestClient(_create_app(_settings(tmp_path))) as client:
        response = client.post("/api/sources/preview", files=_upload("support.json", invalid))
        sources = client.get("/api/sources")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_record"
    assert "گفت‌وگو" in response.json()["detail"]["message"]
    assert sources.json() == []


def test_import_rejects_malformed_csv_and_invalid_json_unicode(tmp_path) -> None:
    settings = _settings(tmp_path)
    malformed_csv = b'q,a\nquestion,"unterminated answer'
    lone_surrogate = b'[{"question":"\\ud800","answer":"answer"}]'
    mapping = json.dumps({"question": "q", "answer": "a"})
    with TestClient(_create_app(settings)) as client:
        csv_response = client.post(
            "/api/sources/import",
            files=_upload("support.csv", malformed_csv, "text/csv"),
            data={"mapping_json": mapping},
        )
        json_response = client.post(
            "/api/sources/import",
            files=_upload("support.json", lone_surrogate, "application/json"),
        )
        sources = client.get("/api/sources")

    assert csv_response.status_code == 422
    assert csv_response.json()["detail"]["code"] == "invalid_csv"
    assert json_response.status_code == 422
    assert json_response.json()["detail"]["code"] == "invalid_unicode"
    assert sources.json() == []


def test_rejects_unsupported_and_oversized_uploads(tmp_path) -> None:
    too_large = b"x" * (5 * 1024 * 1024 + 1)
    with TestClient(_create_app(_settings(tmp_path))) as client:
        unsupported = client.post(
            "/api/sources/preview", files=_upload("support.pdf", b"not supported")
        )
        oversized = client.post(
            "/api/sources/preview", files=_upload("support.txt", too_large, "text/plain")
        )

    assert unsupported.status_code == 422
    assert unsupported.json()["detail"]["code"] == "unsupported_format"
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "file_too_large"


def test_long_original_filename_keeps_its_supported_extension(tmp_path) -> None:
    filename = f"{'x' * 200}.json"
    with TestClient(_create_app(_settings(tmp_path))) as client:
        response = client.post("/api/sources/preview", files=_json_upload(filename))

    assert response.status_code == 200
    assert response.json()["format"] == "json"


def test_interrupted_import_becomes_retryable_and_retry_reuses_source(tmp_path) -> None:
    settings = _settings(tmp_path)
    with TestClient(_create_app(settings)) as client:
        imported = _import_json(client)
        source_id = imported["source"]["id"]
        with sqlite3.connect(settings.database_path) as connection:
            connection.execute(
                "UPDATE sources SET status = 'processing' WHERE id = ?", (source_id,)
            )

    with TestClient(_create_app(settings)) as restarted:
        recovered = restarted.get(f"/api/sources/{source_id}")
        retried = restarted.post(f"/api/sources/{source_id}/retry")
        final = restarted.get(f"/api/sources/{source_id}")

    assert recovered.status_code == 200
    assert recovered.json()["source"]["status"] == "failed"
    assert recovered.json()["source"]["error_code"] == "import_interrupted"
    assert recovered.json()["source"]["retryable"] is True
    assert retried.status_code == 200
    assert retried.json()["source"]["id"] == source_id
    assert final.json()["source"]["status"] == "ready"
    assert final.json()["source"]["record_count"] == 1


def test_deleting_source_removes_records_and_original_upload(tmp_path) -> None:
    settings = _settings(tmp_path)
    with TestClient(_create_app(settings)) as client:
        imported = _import_json(client)
        source_id = imported["source"]["id"]
        assert len(list(settings.uploads_dir.iterdir())) == 1
        deleted = client.delete(f"/api/sources/{source_id}")
        detail = client.get(f"/api/sources/{source_id}")
        listed = client.get("/api/sources")

    assert deleted.status_code == 204
    assert detail.status_code == 404
    assert listed.json() == []
    assert list(settings.uploads_dir.iterdir()) == []


def test_upload_write_failure_does_not_publish_an_unrecoverable_source(
    tmp_path, monkeypatch
) -> None:
    import app.sources as sources_module

    settings = _settings(tmp_path)
    original_write_bytes = Path.write_bytes

    def write_then_fail(path: Path, content: bytes) -> int:
        result = original_write_bytes(path, content)
        if path.name.endswith(".tmp"):
            raise OSError("simulated disk interruption")
        return result

    monkeypatch.setattr(sources_module.Path, "write_bytes", write_then_fail)
    with TestClient(_create_app(settings), raise_server_exceptions=False) as client:
        response = client.post("/api/sources/import", files=_json_upload())
        sources = client.get("/api/sources")

    assert response.status_code == 500
    assert sources.json() == []
    assert list(settings.uploads_dir.iterdir()) == []


def test_unlink_failure_keeps_source_and_upload_available_for_retry(tmp_path, monkeypatch) -> None:
    import app.sources as sources_module

    settings = _settings(tmp_path)
    with TestClient(_create_app(settings)) as client:
        imported = _import_json(client)
        source_id = imported["source"]["id"]
        stored_file = next(settings.uploads_dir.iterdir())
        original_unlink = Path.unlink

        def fail_target_unlink(path: Path, *args, **kwargs) -> None:
            if path == stored_file:
                raise PermissionError("simulated locked upload")
            original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(sources_module.Path, "unlink", fail_target_unlink)
        failed_delete = client.delete(f"/api/sources/{source_id}")
        retained = client.get(f"/api/sources/{source_id}")
        assert failed_delete.status_code == 500
        assert retained.status_code == 200
        assert stored_file.exists()

        monkeypatch.setattr(sources_module.Path, "unlink", original_unlink)
        successful_delete = client.delete(f"/api/sources/{source_id}")

    assert successful_delete.status_code == 204
    assert not stored_file.exists()


def test_startup_removes_interrupted_upload_temporary_files(tmp_path) -> None:
    settings = _settings(tmp_path)
    settings.uploads_dir.mkdir(parents=True)
    temporary_upload = settings.uploads_dir / ("a" * 32 + ".json.tmp")
    temporary_upload.write_bytes(b"partial")

    with TestClient(_create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200

    assert not temporary_upload.exists()


def test_upload_directory_uses_environment_override(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "application-data"
    upload_dir = tmp_path / "original-uploads"
    monkeypatch.setenv("SUPPORTRECALL_DATA_DIR", str(data_dir))
    monkeypatch.setenv("SUPPORTRECALL_UPLOADS_DIR", str(upload_dir))

    settings = Settings.from_environment()

    assert settings.uploads_dir == upload_dir.resolve()


def test_import_marks_source_ready_only_after_vector_indexing(tmp_path) -> None:
    settings = _settings(tmp_path)
    index = _MemoryVectorIndex()

    with TestClient(_create_app(settings, index)) as client:
        imported = _import_json(client)

    assert index.status_during_index == "processing"
    assert imported["source"]["status"] == "ready"


def test_failed_index_keeps_source_upload_and_records_retryable(tmp_path) -> None:
    settings = _settings(tmp_path)
    index = _MemoryVectorIndex()
    index.fail_index = True

    with TestClient(_create_app(settings, index)) as client:
        failed = client.post("/api/sources/import", files=_json_upload())
        sources = client.get("/api/sources").json()
        source_id = sources[0]["id"]
        detail = client.get(f"/api/sources/{source_id}").json()
        assert len(list(settings.uploads_dir.iterdir())) == 1

        index.fail_index = False
        retried = client.post(f"/api/sources/{source_id}/retry")

    assert failed.status_code == 503
    assert failed.json()["detail"]["code"] == "embedding_unavailable"
    assert sources[0]["status"] == "failed"
    assert sources[0]["retryable"] is True
    assert len(detail["records"]) == 1
    assert retried.status_code == 200
    assert retried.json()["source"]["status"] == "ready"
    assert index.sources == {source_id}


def test_delete_keeps_source_and_upload_when_vector_deletion_fails(tmp_path) -> None:
    settings = _settings(tmp_path)
    index = _MemoryVectorIndex()

    with TestClient(_create_app(settings, index)) as client:
        imported = _import_json(client)
        source_id = imported["source"]["id"]
        stored_upload = next(settings.uploads_dir.iterdir())
        index.fail_delete = True

        failed = client.delete(f"/api/sources/{source_id}")
        retained = client.get(f"/api/sources/{source_id}")

    assert failed.status_code == 500
    assert retained.status_code == 200
    assert stored_upload.is_file()
    assert source_id in index.sources
