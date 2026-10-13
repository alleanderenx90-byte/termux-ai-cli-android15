#!/usr/bin/env python3
"""Interactive and one-shot AI chat CLI for Termux.

Usage:
    python scripts/ai_cli.py                      # interactive REPL
    python scripts/ai_cli.py -p "Explain recursion"   # one-shot answer
    echo "Explain recursion" | python scripts/ai_cli.py  # prompt from stdin
    python scripts/ai_cli.py -a -p "hi"           # plain answer only (scriptable)

Set your API keys in .env (see .env.example) or export them directly.
"""
import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("python-dotenv is not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("openai package is not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("anthropic package is not installed. Run: pip install -r requirements.txt")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# Model per provider, overridable with --model.
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
}

PROVIDER_CHOICES = {
    "1": "openai",
    "2": "anthropic",
}

ENV_VARS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ai_cli",
        description="Chat with OpenAI or Anthropic from the terminal.",
        epilog="Without --prompt the script starts an interactive session.",
    )
    parser.add_argument(
        "-p",
        "--prompt",
        help="Prompt to answer once, then exit (piping stdin works too)",
    )
    parser.add_argument(
        "--provider",
        choices=sorted(DEFAULT_MODELS),
        help="Provider to use (skips the interactive picker)",
    )
    parser.add_argument(
        "--model",
        help="Override the model name for the chosen provider",
    )
    parser.add_argument(
        "-a",
        "--answer-only",
        action="store_true",
        help="Print only the answer, no prefix - useful in scripts and pipes",
    )
    return parser


def get_provider_choice():
    print("Choose AI provider:")
    print("1) OpenAI")
    print("2) Anthropic")

    for _ in range(3):
        choice = input("Enter 1 or 2: ").strip()
        if choice in PROVIDER_CHOICES:
            return PROVIDER_CHOICES[choice]
        print(f"'{choice}' is not a valid choice. Please enter 1 or 2.")

    print("Too many invalid attempts, defaulting to OpenAI.")
    return "openai"


def resolve_provider(args):
    """--provider wins, then AI_PROVIDER from the environment, then the picker."""
    if args.provider:
        return args.provider
    from_env = os.getenv("AI_PROVIDER", "").strip().lower()
    if from_env in DEFAULT_MODELS:
        return from_env
    if not sys.stdin.isatty():
        # Piped input without a picker: default rather than fail on read.
        return "openai"
    return get_provider_choice()


def resolve_model(provider, requested):
    return requested or DEFAULT_MODELS[provider]


def chat(provider: str, prompt: str, model: str = None) -> str:
    """Send one prompt and return the answer text."""
    api_key = os.getenv(ENV_VARS[provider])
    if not api_key:
        raise RuntimeError(f"{ENV_VARS[provider]} is missing. Add it to .env")

    model = resolve_model(provider, model)

    if provider == "openai":
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=512,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text += block.text
    return text.strip() or "No response returned."


# Kept as thin aliases so existing imports and the test suite keep working.
def openai_chat(prompt: str):
    return chat("openai", prompt)


def anthropic_chat(prompt: str):
    return chat("anthropic", prompt)


def run_one_shot(args, provider, prompt):
    prompt = prompt.strip()
    if not prompt:
        print("Error: the prompt is empty.", file=sys.stderr)
        return 1

    try:
        answer = chat(provider, prompt, model=args.model)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Check your .env file and API keys.", file=sys.stderr)
        return 1

    if args.answer_only:
        print(answer)
    else:
        print(f"\nAI> {answer}")
    return 0


def run_interactive(provider, model):
    print(f"Using provider: {provider} (model: {resolve_model(provider, model)})")
    print("Type 'exit' or 'quit' to end the session.")

    while True:
        try:
            prompt = input("\nPrompt> ").strip()
        except EOFError:
            print()
            break

        if not prompt:
            continue
        if prompt.lower() in {"exit", "quit"}:
            break

        try:
            answer = chat(provider, prompt, model=model)
            print(f"\nAI> {answer}")
        except Exception as exc:
            print(f"\nError: {exc}")
            print("Check your .env file and API keys.")


def main(argv=None):
    args = build_parser().parse_args(argv)
    provider = resolve_provider(args)

    # Precedence: --prompt, then piped stdin, then interactive.
    if args.prompt is not None:
        return run_one_shot(args, provider, args.prompt)
    if not sys.stdin.isatty():
        return run_one_shot(args, provider, sys.stdin.read())

    run_interactive(provider, args.model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
