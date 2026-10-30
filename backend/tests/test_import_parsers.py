from __future__ import annotations

from pathlib import Path

import pytest

from app.imports.parsers import (
    Conversation,
    CsvColumnMapping,
    ImportParseError,
    Message,
    inspect_csv_columns,
    parse_import,
)


def test_parses_csv_using_explicit_mapping_and_preserves_metadata() -> None:
    content = (
        "شناسه,تاریخ,محصول,دسته,پرسش مشتری,پاسخ پشتیبانی\n"
        "گفتگو-۱,2026-10-28,صورتحساب,پرداخت,چرا مبلغ دوبار کم شد؟,یک پرداخت برگشت داده شد.\n"
    ).encode("utf-8-sig")
    mapping = CsvColumnMapping(
        question="پرسش مشتری",
        answer="پاسخ پشتیبانی",
        conversation_id="شناسه",
        date="تاریخ",
        product="محصول",
        category="دسته",
    )

    result = parse_import("نمونه.csv", content, mapping)

    assert result.format == "csv"
    assert result.columns == ("شناسه", "تاریخ", "محصول", "دسته", "پرسش مشتری", "پاسخ پشتیبانی")
    assert result.records == (
        Conversation(
            conversation_id="گفتگو-۱",
            date="2026-10-28",
            product="صورتحساب",
            category="پرداخت",
            messages=(
                Message(role="customer", content="چرا مبلغ دوبار کم شد؟"),
                Message(role="support", content="یک پرداخت برگشت داده شد."),
            ),
        ),
    )


def test_csv_requires_question_and_answer_mapping() -> None:
    content = "پرسش,پاسخ\nپرسش نمونه,پاسخ نمونه\n".encode("utf-8")

    with pytest.raises(ImportParseError) as error:
        parse_import("support.csv", content)

    assert error.value.code == "mapping_required"
    assert "پرسش" in error.value.message


def test_parses_json_question_answer_records_without_guessing_dates() -> None:
    content = '''[
      {
        "conversation_id": "support-101",
        "product": "حساب کاربری",
        "category": "ورود",
        "question": "چرا کد ورود نمی‌رسد؟",
        "answer": "پوشه پیامک‌های مسدودشده را بررسی کنید."
      }
    ]'''.encode("utf-8")

    result = parse_import("support.json", content)

    assert result.records == (
        Conversation(
            conversation_id="support-101",
            date=None,
            product="حساب کاربری",
            category="ورود",
            messages=(
                Message(role="customer", content="چرا کد ورود نمی‌رسد؟"),
                Message(role="support", content="پوشه پیامک‌های مسدودشده را بررسی کنید."),
            ),
        ),
    )


def test_parses_json_message_conversations_in_original_order() -> None:
    content = '''[
      {
        "conversation_id": "support-102",
        "date": "2026-10-27",
        "messages": [
          {"role": "customer", "content": "سفارشم کجاست؟"},
          {"role": "support", "content": "کد سفارش را می‌فرستید؟"},
          {"role": "customer", "content": "کد آن ۱۲۳۴ است."},
          {"role": "support", "content": "بسته امروز تحویل پست شد."}
        ]
      }
    ]'''.encode("utf-8")

    result = parse_import("support.json", content)

    assert result.records[0].messages == (
        Message(role="customer", content="سفارشم کجاست؟"),
        Message(role="support", content="کد سفارش را می‌فرستید؟"),
        Message(role="customer", content="کد آن ۱۲۳۴ است."),
        Message(role="support", content="بسته امروز تحویل پست شد."),
    )


def test_parses_persian_text_blocks_and_optional_metadata() -> None:
    content = """گفتگو: support-103
تاریخ: 2026-10-26
محصول: سفارش‌ها
دسته‌بندی: ارسال
مشتری: مرسوله هنوز نرسیده است.
پشتیبانی: مرسوله امروز از مرکز توزیع خارج شد.
مشتری: ممنون از پیگیری.
پشتیبانی: خواهش می‌کنم، وضعیت تا امشب به‌روز می‌شود.
---
گفتگو: support-104
مشتری: چطور نشانی را تغییر بدهم؟
پشتیبانی: پیش از ارسال از بخش سفارش‌ها نشانی را ویرایش کنید.
""".encode("utf-8")

    result = parse_import("support.txt", content)

    assert result.format == "text"
    assert result.records[0] == Conversation(
        conversation_id="support-103",
        date="2026-10-26",
        product="سفارش‌ها",
        category="ارسال",
        messages=(
            Message(role="customer", content="مرسوله هنوز نرسیده است."),
            Message(role="support", content="مرسوله امروز از مرکز توزیع خارج شد."),
            Message(role="customer", content="ممنون از پیگیری."),
            Message(role="support", content="خواهش می‌کنم، وضعیت تا امشب به‌روز می‌شود."),
        ),
    )
    assert result.records[1].date is None


@pytest.mark.parametrize(
    ("filename", "content", "code"),
    [
        ("empty.json", b"  \n", "empty_file"),
        ("broken.json", b"{no json", "invalid_json"),
        ("support.pdf", b"irrelevant", "unsupported_format"),
    ],
)
def test_rejects_empty_malformed_or_unsupported_input(
    filename: str, content: bytes, code: str
) -> None:
    with pytest.raises(ImportParseError) as error:
        parse_import(filename, content)

    assert error.value.code == code
    assert error.value.message


def test_inspects_csv_columns_before_the_user_maps_them() -> None:
    content = "شناسه,پرسش,پاسخ\n".encode("utf-8-sig")

    assert inspect_csv_columns(content) == ("شناسه", "پرسش", "پاسخ")


def test_csv_mapping_uses_trimmed_header_names() -> None:
    content = " پرسش مشتری , پاسخ پشتیبانی \nسؤال نمونه,پاسخ نمونه\n".encode("utf-8")
    mapping = CsvColumnMapping(question="پرسش مشتری", answer="پاسخ پشتیبانی")

    result = parse_import("support.csv", content, mapping)

    assert result.records[0].messages == (
        Message(role="customer", content="سؤال نمونه"),
        Message(role="support", content="پاسخ نمونه"),
    )


def test_rejects_json_records_without_a_question_answer_pair() -> None:
    content = (
        b'[{"conversation_id":"missing-answer",'
        b'"question":"\xd9\xbe\xd8\xb1\xd8\xb3\xd8\xb4"}]'
    )

    with pytest.raises(ImportParseError) as error:
        parse_import("support.json", content)

    assert error.value.code == "invalid_record"
    assert error.value.message


def test_synthetic_persian_samples_match_the_documented_parsers() -> None:
    sample_dir = Path(__file__).resolve().parents[2] / "frontend" / "public" / "samples"
    csv_path = sample_dir / "نمونه-پشتیبانی.csv"
    json_path = sample_dir / "نمونه-پشتیبانی.json"
    text_path = sample_dir / "نمونه-پشتیبانی.txt"

    csv_result = parse_import(
        csv_path.name,
        csv_path.read_bytes(),
        CsvColumnMapping(
            question="پرسش مشتری",
            answer="پاسخ پشتیبانی",
            conversation_id="شناسه گفت‌وگو",
            date="تاریخ",
            product="محصول",
            category="دسته‌بندی",
        ),
    )
    json_result = parse_import(json_path.name, json_path.read_bytes())
    text_result = parse_import(text_path.name, text_path.read_bytes())

    assert len(csv_result.records) == 2
    assert len(json_result.records) == 2
    assert len(text_result.records) == 2
    assert all(
        any("پ" in message.content for message in row.messages)
        for row in text_result.records
    )
