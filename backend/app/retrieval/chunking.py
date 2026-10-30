"""Format and split one conversation into searchable text chunks."""

from __future__ import annotations

from collections.abc import Sequence

from app.imports.parsers import Message


def chunk_conversation(
    messages: Sequence[Message], max_chars: int = 1200, overlap_chars: int = 150
) -> list[str]:
    """Format speaker turns and split them with a small overlapping context."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be between zero and max_chars")

    turns = []
    for message in messages:
        speaker = "Customer" if message.role == "customer" else "Support"
        turns.append(f"{speaker}: {message.content.strip()}")
    text = "\n".join(turns).strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary = _last_whitespace(text, start, end)
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break

        next_start = max(start + 1, end - overlap_chars)
        while next_start < end and not text[next_start].isspace():
            next_start += 1
        while next_start < len(text) and text[next_start].isspace():
            next_start += 1
        start = next_start

    return chunks


def _last_whitespace(text: str, start: int, end: int) -> int:
    """Return the last whitespace position before end, or end if absent."""
    for position in range(end - 1, start, -1):
        if text[position].isspace():
            return position
    return end
