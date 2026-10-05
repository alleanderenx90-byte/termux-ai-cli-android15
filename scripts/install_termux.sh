#!/usr/bin/env bash
set -e

pkg update && pkg upgrade -y
pkg install -y git curl wget build-essential python python-pip cmake clang termux-tools

python -m venv ai-env
source ai-env/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

printf '\nSetup complete.\n'
printf 'Next: copy .env.example to .env and add your API keys.\n'
printf 'Then run: python scripts/ai_cli.py\n'
