#!/usr/bin/env python3
"""Local LLM chat CLI using llama.cpp.

Install the optional dependency:
    pip install llama-cpp-python

Place GGUF models in the models/ directory, for example:
    models/tinyllama-1.1b-1t-openorca.Q4_K_M.gguf

Usage:
    python scripts/local_llm.py                          # pick a model, then chat
    python scripts/local_llm.py -p "Explain recursion"  # one-shot answer
    cat notes.txt | python scripts/local_llm.py -a       # prompt from stdin
    python scripts/local_llm.py --list-models            # what is available
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# MODEL_DIR can be overridden in .env; default to <repo>/models.
try:
    from dotenv import load_dotenv

    ENV_FILE = ROOT / ".env"
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
except ImportError:
    pass  # MODEL_DIR can still come from the real environment

MODEL_DIR = Path(os.getenv("MODEL_DIR") or (ROOT / "models"))

# Tried in order when no --model is given.
PREFERRED_MODELS = [
    "tinyllama-1.1b-1t-openorca.Q4_K_M.gguf",
    "llama-2-7b-chat.Q4_K_M.gguf",
    "mistral-7b-instruct-v0.1.Q4_K_M.gguf",
]

EXIT_COMMANDS = {"exit", "quit"}


def _fail(message, hint=None):
    print(f"Error: {message}", file=sys.stderr)
    if hint:
        print(hint, file=sys.stderr)
    return 1


def list_models():
    """Every GGUF file in MODEL_DIR, sorted by size ascending."""
    if not MODEL_DIR.is_dir():
        return []
    return sorted(
        (p for p in MODEL_DIR.glob("*.gguf") if p.is_file()),
        key=lambda p: p.stat().st_size,
    )


def resolve_model_path(requested):
    """Return the model path to load, or None with the reason printed."""
    if requested:
        path = Path(requested)
        # A bare name is looked up in MODEL_DIR, an absolute or relative
        # path with a separator is used as given.
        if len(path.parts) == 1:
            path = MODEL_DIR / requested
        if not path.is_file():
            return None, f"model not found: {path}"
        return path, None

    available = list_models()
    if not available:
        return None, (
            f"no GGUF models found in {MODEL_DIR}\n"
            "Download a small quantized model (for example tinyllama-1.1b-1t-openorca.Q4_K_M.gguf)\n"
            "and place it in that directory, or pass --model with an explicit path."
        )
    for name in PREFERRED_MODELS:
        for path in available:
            if path.name == name:
                return path, None
    return available[0], None  # smallest available model


def build_parser():
    parser = argparse.ArgumentParser(
        prog="local_llm",
        description="Chat with a local GGUF model via llama.cpp.",
        epilog="Without --prompt the script starts an interactive session.",
    )
    parser.add_argument(
        "-p", "--prompt",
        help="Prompt to answer once, then exit (piping stdin works too)",
    )
    parser.add_argument(
        "--model",
        help="Model name in the models directory, or an explicit path to a .gguf file",
    )
    parser.add_argument(
        "-c", "--context",
        type=int, default=2048,
        help="Context window size in tokens (default: 2048)",
    )
    parser.add_argument(
        "-t", "--threads",
        type=int,
        help="CPU threads to use (default: half of the available cores)",
    )
    parser.add_argument(
        "--temp",
        type=float, default=0.7,
        help="Sampling temperature (default: 0.7)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int, default=200,
        help="Maximum tokens to generate per answer (default: 200)",
    )
    parser.add_argument(
        "-a", "--answer-only",
        action="store_true",
        help="Print only the answer, no prefix - useful in scripts and pipes",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List the GGUF models found in the models directory and exit",
    )
    return parser


def load_llm(model_path, args):
    """Import llama_cpp lazily so --list-models works without the package."""
    try:
        from llama_cpp import Llama
    except ImportError:
        return None, _fail(
            "llama-cpp-python is not installed.",
            "Install it with: pip install llama-cpp-python",
        )

    threads = args.threads or max(1, (os.cpu_count() or 1) // 2)
    try:
        return Llama(
            model_path=str(model_path),
            n_ctx=args.context,
            n_threads=threads,
        ), None
    except Exception as exc:
        return None, _fail(f"could not load {model_path.name}: {exc}")


def generate(llm, prompt, args):
    result = llm(
        prompt,
        max_tokens=args.max_tokens,
        temperature=args.temp,
        stop=["User:", "\n\n"],
    )
    return result["choices"][0]["text"].strip()


def run_one_shot(llm, args, prompt):
    prompt = prompt.strip()
    if not prompt:
        return _fail("the prompt is empty.")
    try:
        answer = generate(llm, prompt, args)
    except Exception as exc:
        return _fail(f"generation failed: {exc}")
    if args.answer_only:
        print(answer)
    else:
        print(f"\nAI> {answer}")
    return 0


def run_interactive(llm, model_path, args):
    print(f"Model: {model_path.name}")
    print("Type 'exit' or 'quit' to end the session.")

    while True:
        try:
            prompt = input("\nPrompt> ").strip()
        except EOFError:
            print()
            break
        if not prompt:
            continue
        if prompt.lower() in EXIT_COMMANDS:
            break
        try:
            answer = generate(llm, prompt, args)
        except Exception as exc:
            print(f"\nError: {exc}")
            continue
        print(f"\nAI> {answer}")
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.list_models:
        available = list_models()
        if not available:
            return _fail(f"no GGUF models found in {MODEL_DIR}")
        print(f"Models in {MODEL_DIR}:")
        for path in available:
            print(f"  {path.name}  ({path.stat().st_size / 1024 / 1024:.0f} MB)")
        return 0

    model_path, error = resolve_model_path(args.model)
    if model_path is None:
        return _fail(error)

    llm, error = load_llm(model_path, args)
    if llm is None:
        return error

    if args.prompt is not None:
        return run_one_shot(llm, args, args.prompt)
    if not sys.stdin.isatty():
        return run_one_shot(llm, args, sys.stdin.read())

    return run_interactive(llm, model_path, args)


if __name__ == "__main__":
    sys.exit(main())
