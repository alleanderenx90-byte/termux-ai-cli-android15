#!/usr/bin/env python3
"""Simple local LLM test using llama.cpp.

Install optional dependency:
    pip install llama-cpp-python

Place a GGUF model in the models/ directory, for example:
    models/llama-2-7b-chat.Q4_K_M.gguf
"""

from pathlib import Path
import os
import sys

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
MODEL_DIR.mkdir(exist_ok=True)

try:
    from llama_cpp import Llama
except ImportError:
    print("llama-cpp-python is not installed.")
    print("Install it with: pip install llama-cpp-python")
    sys.exit(1)

candidate = [
    MODEL_DIR / "llama-2-7b-chat.Q4_K_M.gguf",
    MODEL_DIR / "tinyllama-1.1b-1t-openorca.Q4_K_M.gguf",
    MODEL_DIR / "mistral-7b-instruct-v0.1.Q4_K_M.gguf",
]
model_path = next((p for p in candidate if p.exists()), None)

if model_path is None:
    print("No GGUF model found in models/.")
    print("Download a small quantized model and place it in the models/ folder.")
    sys.exit(1)

print(f"Loading model: {model_path}")
llm = Llama(
    model_path=str(model_path),
    n_ctx=2048,
    n_threads=max(1, (os.cpu_count() or 1) // 2),
)

while True:
    prompt = input("\nPrompt> ").strip()
    if not prompt:
        continue
    if prompt.lower() in {"exit", "quit"}:
        break

    result = llm(
        prompt,
        max_tokens=200,
        temperature=0.7,
        stop=["User:", "\n\n"],
    )
    print("\nAI> " + result["choices"][0]["text"].strip())
