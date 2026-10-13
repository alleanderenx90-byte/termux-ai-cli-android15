"""Tests for scripts/ai_cli.py provider selection and prompt handling.

Run with:  python -m pytest -q     (from the repository root)
"""
import builtins
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ai_cli  # noqa: E402


def test_valid_choice_selects_anthropic(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "2")
    assert ai_cli.get_provider_choice() == "anthropic"


def test_valid_choice_selects_openai(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "1")
    assert ai_cli.get_provider_choice() == "openai"


def test_invalid_choice_reprompts_then_succeeds(monkeypatch):
    answers = iter(["3", "abc", "2"])
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(answers))
    assert ai_cli.get_provider_choice() == "anthropic"


def test_repeated_invalid_choices_fall_back_to_openai(monkeypatch):
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "nope")
    assert ai_cli.get_provider_choice() == "openai"


def test_openai_chat_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ai_cli.openai_chat("hello")


def test_anthropic_chat_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        ai_cli.anthropic_chat("hello")


def test_anthropic_chat_concatenates_text_blocks(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class Block:
        def __init__(self, text):
            self.type = "text"
            self.text = text

    class Response:
        content = [Block("part one "), Block("part two")]

    class Messages:
        def create(self, **_kwargs):
            return Response()

    class FakeClient:
        messages = Messages()

    captured = {}

    class FakeAnthropic:
        def __init__(self, api_key=None):
            captured["api_key"] = api_key

        messages = Messages()

    monkeypatch.setattr(ai_cli.anthropic, "Anthropic", FakeAnthropic)
    assert ai_cli.anthropic_chat("hi") == "part one part two"
    assert captured["api_key"] == "test-key"


def test_main_exits_cleanly_on_eof(monkeypatch, capsys):
    """Ctrl-D must end the session without raising or a traceback."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": (_ for _ in ()).throw(EOFError()))
    monkeypatch.setattr(ai_cli, "get_provider_choice", lambda: "openai")
    ai_cli.main()  # must return, not raise
    out = capsys.readouterr().out
    assert "Using provider: openai" in out
