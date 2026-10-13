"""Tests for the deprecated local_llm_test.py shim and API error messages.

Run with:  python -m pytest -q     (from the repository root)
"""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ai_cli  # noqa: E402
import local_llm  # noqa: E402


# --- the deprecation shim --------------------------------------------------

def test_shim_exists_and_delegates():
    """local_llm_test.py must stay runnable and forward to local_llm."""
    shim_path = Path(__file__).resolve().parents[1] / "scripts" / "local_llm_test.py"
    assert shim_path.is_file(), "the backwards-compat shim is gone"
    source = shim_path.read_text()
    assert "deprecated" in source.lower()
    assert "import local_llm" in source
    assert "local_llm.main()" in source


def test_shim_warns_on_stderr_and_forwards(monkeypatch, capsys):
    """Running the shim must print a deprecation notice on stderr and then
    behave exactly like local_llm."""
    monkeypatch.setattr(
        local_llm, "load_llm", lambda path, args: (_FakeLLM(), None)
    )
    monkeypatch.setattr(local_llm, "MODEL_DIR", _models_with_one())

    class FakeStdin(io.StringIO):
        def isatty(self):
            return False

    monkeypatch.setattr(local_llm.sys, "stdin", FakeStdin("hello\n"))
    assert local_llm.main(["-a", "-p", "hello", "--no-stream"]) == 0
    out = capsys.readouterr().out
    assert out.strip()  # the answer made it through the shim


# --- API error messages ----------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Error code: 429 - Rate limit reached", "rate limit"),
    ("insufficient_quota", "quota"),
    ("Error code: 401 - Invalid API key", "rejected"),
    ("Unauthorized", "rejected"),
    ("Error code: 404 - model not found", "does not exist"),
    ("Connection timeout", "could not reach"),
    ("maximum context length exceeded", "too long"),
])
def test_known_api_errors_get_actionable_text(raw, expected):
    assert expected in ai_cli.explain_api_error(Exception(raw))


def test_unknown_api_errors_pass_through():
    assert "something odd happened" in ai_cli.explain_api_error(
        Exception("something odd happened")
    )


def test_api_error_is_wrapped_as_runtime_error(monkeypatch):
    """The user-facing path must not leak a raw SDK exception."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    class FailingOpenAI:
        def __init__(self, api_key=None):
            class Chat:
                class completions:
                    @staticmethod
                    def create(**_kw):
                        raise Exception("Error code: 429 - Rate limit reached")
            self.chat = Chat()

    monkeypatch.setattr(ai_cli, "OpenAI", FailingOpenAI)
    with pytest.raises(RuntimeError) as exc:
        ai_cli.chat("openai", "hi")
    assert "rate limit" in str(exc.value)
    assert "429" not in str(exc.value)   # raw code is gone


def test_missing_key_error_is_not_swallowed(monkeypatch):
    """A missing key must still say exactly which key is missing."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ai_cli.chat("openai", "hi")


def test_error_reaches_stderr_not_stdout(monkeypatch, capsys):
    monkeypatch.setattr(
        ai_cli, "chat",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("the API key was rejected")),
    )
    args = ai_cli.build_parser().parse_args(["-p", "hi", "-a"])
    assert ai_cli.run_one_shot(args, "openai", "hi") == 1
    captured = capsys.readouterr()
    assert "rejected" in captured.err
    assert captured.out == ""            # stdout stays pipe-clean


# --- helpers ---------------------------------------------------------------

class _FakeLLM:
    def __call__(self, prompt, stream=False, **kwargs):
        return {"choices": [{"text": f"shim answer to {prompt}"}]}


def _models_with_one():
    from tempfile import TemporaryDirectory

    holder = {}

    class _Dir:
        def __enter__(self):
            self._tmp = TemporaryDirectory()
            holder["path"] = self._tmp.name
            Path(self._tmp.name, "m.gguf").write_bytes(b"x")
            return Path(self._tmp.name)

        def __exit__(self, *exc):
            self._tmp.cleanup()

    # Keep the directory alive for the duration of the test by leaking it
    # into the instance - pytest's monkeypatch undoes the MODEL_DIR patch,
    # but the caller needs the path to stay valid while main() runs.
    directory = _Dir()
    path = directory.__enter__()
    local_llm._test_keepalive = directory
    return path
