from app.imports.parsers import Message
from app.retrieval.chunking import chunk_conversation


def test_formats_messages_in_order_with_speaker_labels() -> None:
    messages = (
        Message(role="customer", content="I cannot sign in."),
        Message(role="support", content="Please reset your password."),
    )

    assert chunk_conversation(messages) == [
        "Customer: I cannot sign in.\nSupport: Please reset your password."
    ]


def test_empty_messages_return_no_chunks() -> None:
    assert chunk_conversation(()) == []


def test_short_message_returns_one_chunk() -> None:
    assert chunk_conversation((Message(role="customer", content="Hello"),)) == [
        "Customer: Hello"
    ]


def test_long_message_chunks_stay_within_character_limit_and_overlap() -> None:
    words = [f"word{number:04d}" for number in range(500)]
    text = " ".join(words)
    chunks = chunk_conversation(
        (Message(role="customer", content=text),), max_chars=1200, overlap_chars=150
    )

    assert len(chunks) > 1
    assert all(len(chunk) <= 1200 for chunk in chunks)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        shared_suffix = max(
            (size for size in range(1, min(len(previous), len(current)) + 1)
             if previous.endswith(current[:size])),
            default=0,
        )
        assert shared_suffix >= 140


def test_long_persian_text_keeps_all_characters_and_limits_chunks() -> None:
    words = [f"گفتگو{number:04d}" for number in range(500)]
    text = " ".join(words)
    chunks = chunk_conversation(
        (Message(role="support", content=text),), max_chars=1200, overlap_chars=150
    )
    joined = " ".join(chunks)

    assert all(len(chunk) <= 1200 for chunk in chunks)
    assert all(word in joined for word in words)
