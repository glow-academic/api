"""Tests for chat scenario formatter."""

from app.infra.chat.format_chat_scenario import format_chat_scenario


def test_format_chat_scenario_includes_statement_text():
    result = format_chat_scenario("Student is upset about grading.")

    assert result == {
        "role": "developer",
        "content": "The following is the scenario for the chat: Student is upset about grading.",
    }


def test_format_chat_scenario_handles_none_as_empty_string():
    result = format_chat_scenario(None)

    assert result == {
        "role": "developer",
        "content": "The following is the scenario for the chat: ",
    }
