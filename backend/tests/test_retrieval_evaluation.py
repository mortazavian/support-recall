import json
import os
import subprocess
import sys
from pathlib import Path


def test_bilingual_evaluation_fixture_covers_same_and_cross_language_queries() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "retrieval_evaluation.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    conversations = {item["conversation_id"]: item for item in fixture["conversations"]}
    queries = fixture["queries"]

    assert fixture["top_k"] == 3
    assert conversations
    assert queries
    assert {query["language"] for query in queries} == {"fa", "en"}
    assert len({query["expected_conversation_id"] for query in queries}) == len(queries)
    assert all(query["expected_conversation_id"] in conversations for query in queries)
    assert any(
        query["language"] == conversations[query["expected_conversation_id"]]["language"]
        for query in queries
    )
    assert any(
        query["language"] != conversations[query["expected_conversation_id"]]["language"]
        for query in queries
    )


def test_documented_evaluator_command_handles_unavailable_ollama(tmp_path) -> None:
    backend_dir = Path(__file__).parents[1]
    environment = os.environ.copy()
    environment["SUPPORTRECALL_DATA_DIR"] = str(tmp_path / "data")
    environment["OLLAMA_BASE_URL"] = "http://127.0.0.1:1"

    result = subprocess.run(
        [sys.executable, "scripts/evaluate_retrieval.py"],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert b"Traceback" not in result.stderr
    assert b"ModuleNotFoundError" not in result.stderr
