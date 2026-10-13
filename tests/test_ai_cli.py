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
    assert ai_cli.DEFAULT_MODELS["openai"] == "gpt-5.4-mini"
    assert ai_cli.DEFAULT_MODELS["anthropic"] == "claude-sonnet-5-5"


def test_resolve_model_uses_requested_override():
    assert ai_cli.resolve_model("openai", "gpt-4o") == "gpt-4o"
    assert ai_cli.resolve_model("openai", None) == ai_cli.DEFAULT_MODELS["openai"]


def test_resolve_model_falls_back_to_ai_model_env(monkeypatch):
    monkeypatch.delenv("AI_MODEL", raising=False)
    assert ai_cli.resolve_model("openai", None) == ai_cli.DEFAULT_MODELS["openai"]
    monkeypatch.setenv("AI_MODEL", "gpt-5.5")
    assert ai_cli.resolve_model("openai", None) == "gpt-5.5"


def test_explicit_model_beats_ai_model_env(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "gpt-5.5")
    assert ai_cli.resolve_model("openai", "gpt-4o") == "gpt-4o"


def test_list_models_shows_defaults(capsys):
    assert ai_cli.list_models() == 0
    out = capsys.readouterr().out
    assert "openai:" in out and "anthropic:" in out
    # The default must be the one that is actually used by default.
    assert ai_cli.DEFAULT_MODELS["openai"] in out
    assert ai_cli.DEFAULT_MODELS["anthropic"] in out
    assert "* = default" in out


def test_list_models_marks_exactly_one_default_per_provider(capsys):
    ai_cli.list_models()
    out = capsys.readouterr().out
    for provider in ai_cli.KNOWN_MODELS:
        # Stop at the next "provider:" header rather than relying on a blank
        # line, so a provider block cannot bleed into the next one.
        block = out.split(f"{provider}:")[1]
        for other in ai_cli.KNOWN_MODELS:
            if other != provider:
                block = block.split(f"\n{other}:")[0]
        marked = [line for line in block.splitlines() if line.startswith(" *")]
        assert len(marked) == 1, (
            f"{provider} must mark exactly one default, got {len(marked)}"
        )
        assert ai_cli.DEFAULT_MODELS[provider] in marked[0]


def test_default_model_is_listed_as_known():
    """A default that is not in the list would be invisible to --list-models."""
    for provider, default in ai_cli.DEFAULT_MODELS.items():
        names = [name for name, _ in ai_cli.KNOWN_MODELS[provider]]
        assert default in names, f"{provider} default {default} is not listed"


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


def test_parser_accepts_max_tokens():
    args = ai_cli.build_parser().parse_args(["-p", "hi", "--max-tokens", "100"])
    assert args.max_tokens == 100


def test_parser_defaults_max_tokens_to_none():
    args = ai_cli.build_parser().parse_args(["-p", "hi"])
    assert args.max_tokens is None


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
    monkeypatch.setattr(ai_cli, "chat", lambda provider, prompt, model=None, max_tokens=None: "the answer")
    args = ai_cli.build_parser().parse_args(["-p", "hi", "-a"])
    assert ai_cli.run_one_shot(args, "openai", "hi") == 0
    out = capsys.readouterr().out
    assert out.strip() == "the answer"          # no "AI>" prefix, no blank lines


def test_one_shot_prints_prefixed_answer(monkeypatch, capsys):
    monkeypatch.setattr(ai_cli, "chat", lambda provider, prompt, model=None, max_tokens=None: "the answer")
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
    monkeypatch.setattr(ai_cli, "chat", lambda provider, prompt, model=None, max_tokens=None: "piped answer")

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
    for flag in ("--prompt", "--provider", "--model", "--answer-only",
                 "--max-tokens", "--list-models", "--version"):
        assert flag in text


def test_list_models_flag_prints_and_exits(monkeypatch, capsys):
    """--list-models must not need a provider or a key."""
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    def explode(*_a, **_k):
        raise AssertionError("must not resolve a provider")
    monkeypatch.setattr(ai_cli, "resolve_provider", explode)
    assert ai_cli.main(["--list-models"]) == 0
    assert "claude-sonnet-5-5" in capsys.readouterr().out


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exc:
        ai_cli.main(["--version"])
    assert exc.value.code == 0
    assert ai_cli.__version__ in capsys.readouterr().out


def test_max_tokens_is_forwarded_to_chat(monkeypatch, capsys):
    """--max-tokens must reach the provider call, not be silently dropped."""
    captured = {}

    def fake_chat(provider, prompt, model=None, max_tokens=None):
        captured["max_tokens"] = max_tokens
        return "ok"

    monkeypatch.setattr(ai_cli, "chat", fake_chat)
    args = ai_cli.build_parser().parse_args(["-p", "hi", "--max-tokens", "42", "-a"])
    assert ai_cli.run_one_shot(args, "openai", "hi") == 0
    assert captured["max_tokens"] == 42
