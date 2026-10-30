import importlib
import sqlite3

import pytest
from fastapi.testclient import TestClient


def _build_app(data_dir, ollama_base_url="http://localhost:11434"):
    try:
        settings_module = importlib.import_module("app.settings")
        main_module = importlib.import_module("app.main")
    except ModuleNotFoundError as error:
        pytest.fail(f"Backend health implementation is missing: {error.name}", pytrace=False)

    return main_module.create_app(
        settings_module.Settings(data_dir=data_dir, ollama_base_url=ollama_base_url)
    )


def test_health_initializes_persistent_database(tmp_path):
    app = _build_app(tmp_path / "supportrecall-data")

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "storage": "ready",
        "service": "supportrecall",
    }

    database_path = tmp_path / "supportrecall-data" / "supportrecall.sqlite3"
    assert database_path.is_file()
    with sqlite3.connect(database_path) as connection:
        version = connection.execute(
            "SELECT value FROM app_meta WHERE key = ?", ("schema_version",)
        ).fetchone()

    assert version == ("2",)


def test_health_reuses_existing_database(tmp_path):
    data_dir = tmp_path / "supportrecall-data"

    with TestClient(_build_app(data_dir)):
        pass

    database_path = data_dir / "supportrecall.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO app_meta (key, value) VALUES (?, ?)",
            ("test_sentinel", "survives_restart"),
        )

    with TestClient(_build_app(data_dir)) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    with sqlite3.connect(database_path) as connection:
        sentinel = connection.execute(
            "SELECT value FROM app_meta WHERE key = ?", ("test_sentinel",)
        ).fetchone()

    assert sentinel == ("survives_restart",)


def test_health_does_not_require_ollama_to_be_running(tmp_path):
    app = _build_app(tmp_path / "supportrecall-data", "http://127.0.0.1:1")

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
