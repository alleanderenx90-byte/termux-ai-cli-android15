"""Tests for scripts/ai_cli.py provider selection, prompt handling and the CLI.

Run with:  python -m pytest -q     (from the repository root)
"""
import builtins
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ai_cli  # noqa: E402


# --- provider picker -------------------------------------------------------

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


# --- key handling ----------------------------------------------------------

@pytest.mark.parametrize("provider,env_var", [
    ("openai", "OPENAI_API_KEY"),
    ("anthropic", "ANTHROPIC_API_KEY"),
])
def test_chat_requires_key(monkeypatch, provider, env_var):
    monkeypatch.delenv(env_var, raising=False)
    with pytest.raises(RuntimeError, match=env_var):
        ai_cli.chat(provider, "hello")


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

    class FakeAnthropic:
        def __init__(self, api_key=None):
            self.api_key = api_key

        messages = Messages()

    captured = {}
    real = ai_cli.anthropic.Anthropic
    ai_cli.anthropic.Anthropic = lambda api_key=None: captured.setdefault(
        "client", FakeAnthropic(api_key=api_key)
    )
    try:
        assert ai_cli.chat("anthropic", "hi") == "part one part two"
    finally:
        ai_cli.anthropic.Anthropic = real
    assert captured["client"].api_key == "test-key"


def test_model_defaults_per_provider():
    assert ai_cli.DEFAULT_MODELS["openai"] == "gpt-4o-mini"
    assert ai_cli.DEFAULT_MODELS["anthropic"].startswith("claude")


def test_resolve_model_uses_requested_override():
    assert ai_cli.resolve_model("openai", "gpt-4o") == "gpt-4o"
    assert ai_cli.resolve_model("openai", None) == ai_cli.DEFAULT_MODELS["openai"]


# --- CLI argument parsing --------------------------------------------------

def test_parser_accepts_one_shot_flags():
    args = ai_cli.build_parser().parse_args(
        ["--prompt", "hi", "-a", "--provider", "openai"]
    )
    assert args.prompt == "hi"
    assert args.answer_only is True
    assert args.provider == "openai"
    assert args.model is None


def test_parser_accepts_model_override():
    args = ai_cli.build_parser().parse_args(["-p", "hi", "--model", "gpt-4o"])
    assert args.model == "gpt-4o"


def test_parser_rejects_unknown_provider(capsys):
    with pytest.raises(SystemExit):
        ai_cli.build_parser().parse_args(["-p", "hi", "--provider", "bogus"])
    assert "invalid choice" in capsys.readouterr().err


def test_provider_flag_skips_the_picker(monkeypatch):
    def explode(*_a, **_k):
        raise AssertionError("picker must not run when --provider is given")

    monkeypatch.setattr(builtins, "input", explode)
    args = ai_cli.build_parser().parse_args(["-p", "hi", "--provider", "anthropic"])
    assert ai_cli.resolve_provider(args) == "anthropic"


def test_env_var_sets_provider(monkeypatch):
    args = ai_cli.build_parser().parse_args(["-p", "hi"])
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    assert ai_cli.resolve_provider(args) == "anthropic"


def test_piped_input_without_provider_defaults_to_openai(monkeypatch):
    args = ai_cli.build_parser().parse_args(["-p", "hi"])
    monkeypatch.delenv("AI_PROVIDER", raising=False)

    class FakeStdin:
        @staticmethod
        def isatty():
            return False

    monkeypatch.setattr(ai_cli.sys, "stdin", FakeStdin)
    assert ai_cli.resolve_provider(args) == "openai"


# --- one-shot and main() ---------------------------------------------------

def test_one_shot_prints_plain_answer(monkeypatch, capsys):
    monkeypatch.setattr(ai_cli, "chat", lambda provider, prompt, model=None: "the answer")
    args = ai_cli.build_parser().parse_args(["-p", "hi", "-a"])
    assert ai_cli.run_one_shot(args, "openai", "hi") == 0
    out = capsys.readouterr().out
    assert out.strip() == "the answer"          # no "AI>" prefix, no blank lines


def test_one_shot_prints_prefixed_answer(monkeypatch, capsys):
    monkeypatch.setattr(ai_cli, "chat", lambda provider, prompt, model=None: "the answer")
    args = ai_cli.build_parser().parse_args(["-p", "hi"])
    assert ai_cli.run_one_shot(args, "openai", "hi") == 0
    assert "AI> the answer" in capsys.readouterr().out


def test_one_shot_rejects_empty_prompt(capsys):
    args = ai_cli.build_parser().parse_args(["-p", "   "])
    assert ai_cli.run_one_shot(args, "openai", "   ") == 1
    assert "empty" in capsys.readouterr().err


def test_one_shot_reports_api_errors_on_stderr(monkeypatch, capsys):
    def boom(*_a, **_k):
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to .env")

    monkeypatch.setattr(ai_cli, "chat", boom)
    args = ai_cli.build_parser().parse_args(["-p", "hi"])
    assert ai_cli.run_one_shot(args, "openai", "hi") == 1
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.err
    assert captured.out == ""


def test_main_reads_prompt_from_stdin(monkeypatch, capsys):
    monkeypatch.setattr(ai_cli, "chat", lambda provider, prompt, model=None: "piped answer")

    class FakeStdin(io.StringIO):
        def isatty(self):
            return False

    monkeypatch.setattr(ai_cli.sys, "stdin", FakeStdin("what is 2+2\n"))
    assert ai_cli.main(["-a", "--provider", "openai"]) == 0
    assert capsys.readouterr().out.strip() == "piped answer"


def test_main_exits_cleanly_on_eof(monkeypatch, capsys):
    """Ctrl-D must end the session without raising or a traceback."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": (_ for _ in ()).throw(EOFError()))
    monkeypatch.setattr(ai_cli, "get_provider_choice", lambda: "openai")

    # Under pytest stdin is a DontReadFromInput pipe; present it as a tty so
    # main() takes the interactive path instead of reading stdin.
    class FakeStdin:
        @staticmethod
        def isatty():
            return True

    monkeypatch.setattr(ai_cli.sys, "stdin", FakeStdin)
    assert ai_cli.main([]) == 0
    out = capsys.readouterr().out
    assert "Using provider: openai" in out


def test_main_help_lists_options(capsys):
    with pytest.raises(SystemExit) as exc:
        ai_cli.main(["--help"])
    assert exc.value.code == 0
    text = capsys.readouterr().out
    for flag in ("--prompt", "--provider", "--model", "--answer-only"):
        assert flag in text
