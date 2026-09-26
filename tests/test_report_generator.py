"""
Tests for the AI report generator, using mocked Claude responses.
Never makes a real API call. Specifically covers the bug found during
live testing: Claude's response can include a thinking block before
the text block, and content[0] is not always the text.
"""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")

from ai.report_generator import generate_report, _template_fallback  # noqa: E402


VALID_REPORT_JSON = json.dumps(
    {
        "executive_summary": "Test summary",
        "key_incidents": [],
        "recurring_problems": ["network (3 occurrences)"],
        "risk_observations": [],
        "vendor_observations": [],
        "cost_observations": [],
        "recommended_actions": [],
        "management_attention_items": [],
    }
)


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _thinking_block(text="reasoning..."):
    return SimpleNamespace(type="thinking", text=text)


def test_template_fallback_with_insufficient_data():
    result = _template_fallback({"insufficient_data": True}, {}, [])
    assert result["executive_summary"] == "Insufficient data."
    assert result["generated_by"] == "template_fallback"


def test_no_api_key_uses_template_fallback():
    with patch.dict(os.environ, {}, clear=True):
        result = generate_report("Test Period", {"insufficient_data": True}, {}, [])
    assert result["generated_by"] == "template_fallback"


@patch("anthropic.Anthropic")
def test_generate_report_finds_text_block_after_thinking_block(mock_anthropic_cls):
    # Reproduces the real bug: content[0] is a thinking block, not text.
    mock_message = MagicMock()
    mock_message.content = [_thinking_block(), _text_block(VALID_REPORT_JSON)]
    mock_message.stop_reason = "end_turn"
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    mock_anthropic_cls.return_value = mock_client

    result = generate_report("Test Period", {"insufficient_data": False, "total_tickets": 5}, {}, [])

    assert result["generated_by"] == "claude"
    assert result["executive_summary"] == "Test summary"


@patch("anthropic.Anthropic")
def test_generate_report_strips_markdown_code_fences(mock_anthropic_cls):
    # Models sometimes wrap JSON in ```json ... ``` even when told not to.
    fenced = f"```json\n{VALID_REPORT_JSON}\n```"
    mock_message = MagicMock()
    mock_message.content = [_text_block(fenced)]
    mock_message.stop_reason = "end_turn"
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    mock_anthropic_cls.return_value = mock_client

    result = generate_report("Test Period", {"insufficient_data": False, "total_tickets": 5}, {}, [])

    assert result["generated_by"] == "claude"
    assert result["executive_summary"] == "Test summary"


@patch("anthropic.Anthropic")
def test_generate_report_falls_back_when_no_text_block_present(mock_anthropic_cls):
    mock_message = MagicMock()
    mock_message.content = [_thinking_block()]  # no text block at all
    mock_message.stop_reason = "end_turn"
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    mock_anthropic_cls.return_value = mock_client

    result = generate_report("Test Period", {"insufficient_data": True}, {}, [])

    assert result["generated_by"] == "template_fallback"
    assert "ai_error" in result


@patch("anthropic.Anthropic")
def test_generate_report_falls_back_when_text_block_is_empty(mock_anthropic_cls):
    # Reproduces the real bug: max_tokens exhausted by thinking, text block
    # exists but is an empty string.
    mock_message = MagicMock()
    mock_message.content = [_thinking_block(), _text_block("")]
    mock_message.stop_reason = "max_tokens"
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    mock_anthropic_cls.return_value = mock_client

    result = generate_report("Test Period", {"insufficient_data": True}, {}, [])

    assert result["generated_by"] == "template_fallback"
    assert "ai_error" in result
    assert "max_tokens" in result["ai_error"]


@patch("anthropic.Anthropic")
def test_generate_report_falls_back_on_malformed_json(mock_anthropic_cls):
    mock_message = MagicMock()
    mock_message.content = [_text_block("not valid json")]
    mock_message.stop_reason = "end_turn"
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    mock_anthropic_cls.return_value = mock_client

    result = generate_report("Test Period", {"insufficient_data": True}, {}, [])

    assert result["generated_by"] == "template_fallback"
    assert "ai_error" in result
