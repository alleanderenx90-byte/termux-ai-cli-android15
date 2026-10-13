"""Tests for scripts/local_llm.py model resolution and the CLI.

Run with:  python -m pytest -q     (from the repository root)
"""
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import local_llm  # noqa: E402


@pytest.fixture
def models_dir(tmp_path, monkeypatch):
    """Point MODEL_DIR at a temp directory with controllable contents."""
    monkeypatch.setattr(local_llm, "MODEL_DIR", tmp_path)
    return tmp_path


def _make_model(directory, name, size=1024):
    path = directory / name
    path.write_bytes(b"x" * size)
    return path


# --- model discovery -------------------------------------------------------

def test_list_models_empty_when_dir_missing(models_dir):
    assert local_llm.list_models() == []


def test_list_models_finds_gguf_only(models_dir):
    _make_model(models_dir, "a.gguf")
    models_dir.joinpath("notes.txt").write_text("ignore me")
    names = [p.name for p in local_llm.list_models()]
    assert names == ["a.gguf"]


def test_list_models_sorted_by_size(models_dir):
    _make_model(models_dir, "big.gguf", size=5000)
    _make_model(models_dir, "small.gguf", size=100)
    names = [p.name for p in local_llm.list_models()]
    assert names == ["small.gguf", "big.gguf"]


def test_explicit_path_is_used_as_given(models_dir, tmp_path):
    custom = tmp_path / "elsewhere.gguf"
    custom.write_bytes(b"x")
    args = local_llm.build_parser().parse_args(["--model", str(custom)])
    path, error = local_llm.resolve_model_path(args.model)
    assert error is None
    assert path == custom


def test_bare_name_is_looked_up_in_model_dir(models_dir):
    _make_model(models_dir, "custom.gguf")
    args = local_llm.build_parser().parse_args(["--model", "custom.gguf"])
    path, error = local_llm.resolve_model_path(args.model)
    assert error is None
    assert path == models_dir / "custom.gguf"


def test_missing_explicit_model_reports_error(models_dir):
    args = local_llm.build_parser().parse_args(["--model", "nope.gguf"])
    path, error = local_llm.resolve_model_path(args.model)
    assert path is None
    assert "not found" in error


def test_no_models_reports_helpful_error(models_dir):
    path, error = local_llm.resolve_model_path(None)
    assert path is None
    assert "no GGUF models found" in error
    assert "tinyllama" in error  # suggests a concrete starter model


def test_prefers_tinyllama_over_larger_models(models_dir):
    _make_model(models_dir, "llama-2-7b-chat.Q4_K_M.gguf", size=9000)
    _make_model(models_dir, "tinyllama-1.1b-1t-openorca.Q4_K_M.gguf", size=1000)
    path, error = local_llm.resolve_model_path(None)
    assert error is None
    assert path.name.startswith("tinyllama")


def test_falls_back_to_smallest_when_no_preferred_model(models_dir):
    _make_model(models_dir, "small.gguf", size=100)
    _make_model(models_dir, "large.gguf", size=9000)
    path, error = local_llm.resolve_model_path(None)
    assert error is None
    assert path.name == "small.gguf"


# --- CLI argument parsing --------------------------------------------------

def test_parser_defaults():
    args = local_llm.build_parser().parse_args([])
    assert args.prompt is None
    assert args.model is None
    assert args.context == 2048
    assert args.temp == 0.7
    assert args.max_tokens == 200
    assert args.answer_only is False
    assert args.list_models is False
    assert args.stream is True       # streaming is the default on slow hardware


def test_no_stream_flag_disables_streaming():
    args = local_llm.build_parser().parse_args(["--no-stream"])
    assert args.stream is False


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as exc:
        local_llm.main(["--version"])
    assert exc.value.code == 0
    assert local_llm.__version__ in capsys.readouterr().out


def test_parser_accepts_generation_flags():
    args = local_llm.build_parser().parse_args(
        ["-p", "hi", "--model", "m.gguf", "-c", "4096", "--temp", "0.2", "--max-tokens", "50"]
    )
    assert (args.prompt, args.model, args.context) == ("hi", "m.gguf", 4096)
    assert (args.temp, args.max_tokens) == (0.2, 50)


def test_parser_rejects_non_numeric_context():
    with pytest.raises(SystemExit):
        local_llm.build_parser().parse_args(["-c", "big"])


# --- loading and generation ------------------------------------------------

class FakeLLM:
    """Non-streaming stub; accepts stream= so the new default does not break it."""

    def __init__(self, *args, **kwargs):
        self.init_kwargs = kwargs

    def __call__(self, prompt, stream=False, **kwargs):
        return {"choices": [{"text": f"  answer to: {prompt}  "}]}


def test_load_llm_passes_context_and_threads(monkeypatch):
    monkeypatch.setattr(local_llm, "_fail", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unreachable")))
    monkeypatch.setitem(sys.modules, "llama_cpp", type("m", (), {"Llama": FakeLLM}))
    args = local_llm.build_parser().parse_args(["-c", "4096", "-t", "3"])
    llm, error = local_llm.load_llm(Path("x.gguf"), args)
    assert error is None
    assert llm.init_kwargs["n_ctx"] == 4096
    assert llm.init_kwargs["n_threads"] == 3


def test_load_llm_defaults_threads_to_half_the_cores(monkeypatch):
    monkeypatch.setattr(local_llm, "_fail", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unreachable")))
    monkeypatch.setitem(sys.modules, "llama_cpp", type("m", (), {"Llama": FakeLLM}))
    monkeypatch.setattr(local_llm.os, "cpu_count", lambda: 8)
    args = local_llm.build_parser().parse_args([])
    llm, _ = local_llm.load_llm(Path("x.gguf"), args)
    assert llm.init_kwargs["n_threads"] == 4


def test_generate_strips_whitespace():
    llm = FakeLLM()
    args = local_llm.build_parser().parse_args(["--no-stream"])
    text, streamed = local_llm.generate(llm, "hi", args)
    assert text == "answer to: hi"
    assert streamed is False       # caller must print it


class StreamingLLM:
    """Yields token chunks like llama-cpp-python does with stream=True."""

    def __init__(self, *args, **kwargs):
        self.stream_requested = None

    def __call__(self, prompt, stream=False, **kwargs):
        self.stream_requested = stream
        if stream:
            text = "hello world"
            for word in text.split(" "):
                yield {"choices": [{"text": word + " "}]}
        else:
            return {"choices": [{"text": "whole answer"}]}


def test_generate_streams_token_by_token(capsys):
    llm = StreamingLLM()
    args = local_llm.build_parser().parse_args([])
    answer, streamed = local_llm.generate(llm, "hi", args)
    assert llm.stream_requested is True
    assert answer == "hello world"
    assert streamed is True        # already printed, caller must not re-print
    # tokens appeared as they arrived, not all at the end
    out = capsys.readouterr().out
    assert "hello " in out and "world " in out


def test_generate_falls_back_when_stream_unsupported(capsys):
    """Older llama-cpp-python raises on stream=True - must not crash or
    lose the answer."""

    class NoStreamLLM:
        def __call__(self, prompt, stream=False, **kwargs):
            if stream:
                raise TypeError("stream is not a valid keyword")
            return {"choices": [{"text": "  fallback answer  "}]}

    args = local_llm.build_parser().parse_args([])
    text, streamed = local_llm.generate(NoStreamLLM(), "hi", args)
    assert text == "fallback answer"
    assert streamed is False       # nothing printed yet, caller prints it


# --- main() end to end -----------------------------------------------------

def test_list_models_flag_prints_and_exits(models_dir, capsys):
    _make_model(models_dir, "a.gguf", size=2048)
    assert local_llm.main(["--list-models"]) == 0
    out = capsys.readouterr().out
    assert "a.gguf" in out
    assert "MB" in out


def test_main_reports_missing_model(models_dir, capsys):
    assert local_llm.main(["-p", "hi"]) == 1
    assert "no GGUF models found" in capsys.readouterr().err


def test_main_one_shot_plain_answer(models_dir, monkeypatch, capsys):
    _make_model(models_dir, "m.gguf")
    monkeypatch.setattr(local_llm, "load_llm", lambda path, args: (FakeLLM(), None))
    args = ["-p", "hi", "-a", "--no-stream", "--model", "m.gguf"]
    assert local_llm.main(args) == 0
    assert capsys.readouterr().out.strip() == "answer to: hi"


def test_main_one_shot_prefixed_answer(models_dir, monkeypatch, capsys):
    _make_model(models_dir, "m.gguf")
    monkeypatch.setattr(local_llm, "load_llm", lambda path, args: (FakeLLM(), None))
    assert local_llm.main(["-p", "hi", "--no-stream", "--model", "m.gguf"]) == 0
    assert "AI> answer to: hi" in capsys.readouterr().out


def test_main_reads_prompt_from_stdin(models_dir, monkeypatch, capsys):
    _make_model(models_dir, "m.gguf")
    monkeypatch.setattr(local_llm, "load_llm", lambda path, args: (FakeLLM(), None))

    class FakeStdin(io.StringIO):
        def isatty(self):
            return False

    monkeypatch.setattr(local_llm.sys, "stdin", FakeStdin("what is 2+2\n"))
    assert local_llm.main(["-a", "--no-stream", "--model", "m.gguf"]) == 0
    assert capsys.readouterr().out.strip() == "answer to: what is 2+2"


def test_main_interactive_then_exit(models_dir, monkeypatch, capsys):
    _make_model(models_dir, "m.gguf")
    monkeypatch.setattr(local_llm, "load_llm", lambda path, args: (FakeLLM(), None))

    class FakeStdin(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(local_llm.sys, "stdin", FakeStdin("hello\nexit\n"))
    assert local_llm.main(["--no-stream", "--model", "m.gguf"]) == 0
    out = capsys.readouterr().out
    assert "Model: m.gguf" in out
    assert "AI> answer to: hello" in out


def test_main_exits_cleanly_on_eof(models_dir, monkeypatch, capsys):
    _make_model(models_dir, "m.gguf")
    monkeypatch.setattr(local_llm, "load_llm", lambda path, args: (FakeLLM(), None))

    class FakeStdin(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(local_llm.sys, "stdin", FakeStdin(""))
    assert local_llm.main(["--no-stream", "--model", "m.gguf"]) == 0
    assert "Model: m.gguf" in capsys.readouterr().out


def test_main_help_lists_options(capsys):
    with pytest.raises(SystemExit) as exc:
        local_llm.main(["--help"])
    assert exc.value.code == 0
    text = capsys.readouterr().out
    for flag in ("--prompt", "--model", "--context", "--max-tokens",
                 "--list-models", "--no-stream", "--version"):
        assert flag in text


def test_main_streams_when_answer_only(models_dir, monkeypatch, capsys):
    """-a with streaming must emit only the tokens, no prefix or blank lines."""
    _make_model(models_dir, "m.gguf")
    monkeypatch.setattr(local_llm, "load_llm", lambda path, args: (StreamingLLM(), None))
    assert local_llm.main(["-a", "-p", "hi", "--model", "m.gguf"]) == 0
    assert capsys.readouterr().out.strip() == "hello world"


def test_main_streams_with_prefix_when_not_answer_only(models_dir, monkeypatch, capsys):
    _make_model(models_dir, "m.gguf")
    monkeypatch.setattr(local_llm, "load_llm", lambda path, args: (StreamingLLM(), None))
    assert local_llm.main(["-p", "hi", "--model", "m.gguf"]) == 0
    out = capsys.readouterr().out
    # The stream prints itself; no separate "AI>" line is added.
    assert out.strip() == "hello world"


def test_main_prefix_is_not_duplicated_when_streaming(models_dir, monkeypatch, capsys):
    """Regression: the answer must appear exactly once, with no stray 'AI>'."""
    _make_model(models_dir, "m.gguf")
    monkeypatch.setattr(local_llm, "load_llm", lambda path, args: (StreamingLLM(), None))
    assert local_llm.main(["-p", "hi", "--model", "m.gguf"]) == 0
    out = capsys.readouterr().out
    assert out.count("hello world") == 1
    assert "AI>" not in out
