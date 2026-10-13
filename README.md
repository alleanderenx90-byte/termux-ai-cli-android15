# Termux AI CLI for Android 15

A ready-to-use Termux setup for running AI CLI tools on Android 15.

Features:
- Termux installation and setup
- Python + virtual environment
- OpenAI API CLI
- Anthropic API CLI
- Hugging Face access
- local LLM experiment workflow with llama.cpp
- simple examples and scripts

## Requirements
- Android 15 device
- Termux installed from F-Droid
- Internet connection for package installs and API access
- Optional: OpenAI or Anthropic API key

## 1) Install Termux

Install Termux from F-Droid:

https://f-droid.org/packages/com.termux/

Then open Termux and run:

```bash
pkg update && pkg upgrade -y
pkg install -y git curl wget build-essential python python-pip cmake clang
termux-setup-storage
```

## 2) Set up Python environment

```bash
python -m venv ai-env
source ai-env/bin/activate
pip install --upgrade pip setuptools wheel
```

## 3) Install AI dependencies

```bash
pip install -r requirements.txt
```

## 4) Configure API keys

Copy the example env file and update it:

```bash
cp .env.example .env
```

Edit `.env` and set your keys:

```bash
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
HF_TOKEN=your_huggingface_token_here
```

## 5) Run the AI CLI

Interactive chat CLI:

```bash
python scripts/ai_cli.py
```

The script will let you choose a provider:
- OpenAI
- Anthropic

### One-shot and scripting

Ask a single question without entering the REPL:

```bash
python scripts/ai_cli.py -p "Explain recursion in Python"
```

The prompt can also come from a pipe, and `--provider` / `--model` skip the
interactive picker — handy in scripts and Termux widgets:

```bash
# provider pinned, plain answer only (no "AI>" prefix)
python scripts/ai_cli.py --provider anthropic -p "Summarize this in one line" -a

# pipe a file or command output
cat notes.txt | python scripts/ai_cli.py -a --provider openai
termux-battery-status | python scripts/ai_cli.py -a -p "Explain this status"

# override the model
python scripts/ai_cli.py -p "hi" --model gpt-4o
```

`AI_PROVIDER` in the environment (or `.env`) sets the default provider so you
don't have to pass `--provider` every time. Exit code is `0` on success and `1`
on an error (missing key, empty prompt, API failure); errors go to stderr, so
`-a` output is safe to pipe into other commands.

Use `python scripts/ai_cli.py --help` for the full list of options.

## 6) Local LLM example

For lightweight local models using llama.cpp:

```bash
pip install llama-cpp-python
mkdir -p models
python scripts/local_llm_test.py
```

This script expects a GGUF model in `models/` such as:

```bash
models/llama-2-7b-chat.Q4_K_M.gguf
```

You can download a compatible model from a trusted source and place it in `models/`.

## 7) Suggested workflow

Best practical workflow on Android:
- Use API-based AI for main work
- Use local LLM experiments only for lightweight models
- Keep prompts short and optimized for mobile constraints

## 8) Common notes

- Large local models are slow on Android devices
- API-based models are the most practical solution for real work
- Termux is best for CLI-based workflows, not heavy desktop-style ML tasks

## 9) Files in this repo

- `scripts/ai_cli.py` — interactive AI chat CLI
- `scripts/local_llm_test.py` — local llama.cpp example
- `scripts/install_termux.sh` — minimal setup helper
- `install.sh` — full automated 10-step installer
- `tests/test_ai_cli.py` — unit tests for the CLI helpers
- `.env.example` — sample environment variables
- `requirements.txt` — Python dependencies
- `LICENSE` — MIT

## 10) Development

Run the test suite locally:

```bash
python -m pytest -q
```

CI (`.github/workflows/ci.yml`) runs the syntax checks and tests on every
push to `main` and every pull request.

## 11) Example commands

```bash
# start AI chat
python scripts/ai_cli.py

# quick local LLM test
python scripts/local_llm_test.py

# install Termux packages
bash scripts/install_termux.sh
```

## License

MIT
