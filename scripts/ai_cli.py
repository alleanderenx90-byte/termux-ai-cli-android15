#!/usr/bin/env python3
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

PROVIDERS = {
    "1": "openai",
    "2": "anthropic",
}


def get_provider_choice():
    print("Choose AI provider:")
    print("1) OpenAI")
    print("2) Anthropic")
    choice = input("Enter 1 or 2: ").strip()
    return PROVIDERS.get(choice, "openai")


def openai_chat(prompt: str):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Add it to .env")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def anthropic_chat(prompt: str):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is missing. Add it to .env")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=512,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text += block.text
    return text.strip() or "No response returned."


def main():
    provider = get_provider_choice()
    print(f"Using provider: {provider}")
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
            if provider == "openai":
                answer = openai_chat(prompt)
            else:
                answer = anthropic_chat(prompt)
            print(f"\nAI> {answer}")
        except Exception as exc:
            print(f"\nError: {exc}")
            print("Check your .env file and API keys.")


if __name__ == "__main__":
    main()
