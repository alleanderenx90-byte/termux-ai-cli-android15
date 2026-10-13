#!/usr/bin/env bash
set -euo pipefail

# Termux AI CLI - Full Automated Installation for Android 15
# One-command setup for OpenAI, Anthropic and local LLMs

echo "================================================="
echo "Termux AI CLI - Full Automated Setup"
echo "Android 15 Edition"
echo "================================================="
echo ""

# --- Preflight -----------------------------------------------------------
# Check everything that is needed BEFORE spending ten minutes on package
# updates. Without this, a missing tool only surfaces at step 8, after the
# long steps have already run.
preflight_failed=0

for cmd in pkg python git; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command '$cmd' not found." >&2
    preflight_failed=1
  fi
done

# git is installed by step 2, but only if pkg itself works - a missing pkg
# means nothing below can run at all.
if ! command -v pkg >/dev/null 2>&1; then
  echo "ERROR: 'pkg' not found - this script must run inside Termux." >&2
  echo "       Install Termux from F-Droid and run it there." >&2
  exit 1
fi

if [ "$preflight_failed" -ne 0 ]; then
  echo "Aborting before any changes. See the messages above." >&2
  exit 1
fi

# Warn (do not abort) when the target already exists - a re-run would
# overwrite a working venv and drop installed packages.
PROJECT_DIR="$HOME/ai-projects"
if [ -d "$PROJECT_DIR/ai-env" ]; then
  echo "NOTE: $PROJECT_DIR/ai-env already exists."
  echo "      A re-run will reuse it; remove it first for a clean install."
fi

# Step 1: Update packages
echo "[1/10] Updating Termux packages..."
pkg update -y
pkg upgrade -y

# Step 2: Install system dependencies
echo "[2/10] Installing system dependencies..."
pkg install -y \
  git \
  curl \
  wget \
  build-essential \
  python \
  python-pip \
  cmake \
  clang \
  termux-tools \
  vim \
  nano \
  htop \
  neofetch

# Step 3: Setup storage access
echo "[3/10] Granting storage access..."
termux-setup-storage

# Step 4: Create project directory
# (PROJECT_DIR is already set in the preflight section)
echo "[4/10] Creating project directories..."
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Step 5: Create virtual environment
echo "[5/10] Setting up Python virtual environment..."
python -m venv ai-env
source ai-env/bin/activate

# Step 6: Upgrade pip
echo "[6/10] Upgrading pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel

# Step 7: Install all AI dependencies
echo "[7/10] Installing AI CLI packages..."
# NOTE: `pip` has no `-y` flag - it never prompts, so passing one aborts the
# whole script with "no such option: -y".
#
# Keep this list in sync with requirements.txt and only add what the scripts
# actually import. torch alone is ~2 GB and none of the scripts use it -
# transformers, huggingface_hub, requests, pydantic, typer and rich are
# likewise unused, and every extra package costs install time and storage on
# a phone.
pip install \
  openai \
  anthropic \
  python-dotenv \
  llama-cpp-python

# Step 8: Clone repo and copy scripts
echo "[8/10] Setting up AI CLI scripts..."
if [ ! -d "$PROJECT_DIR/termux-ai-cli" ]; then
  git clone https://github.com/alleanderenx90-byte/termux-ai-cli-android15 termux-ai-cli
fi
# Only the runnable Python scripts belong next to the venv - the installer
# helper is not usable from this location.
cp -v termux-ai-cli/scripts/ai_cli.py \
      termux-ai-cli/scripts/local_llm.py . 2>/dev/null || true

# Step 9: Create .env file
echo "[9/10] Creating .env configuration file..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
  cat > "$PROJECT_DIR/.env" << 'EOF'
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic Configuration
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Default provider for the CLIs: openai or anthropic
AI_PROVIDER=

# Model paths
MODEL_DIR=$HOME/ai-projects/models
EOF
  echo ".env file created at $PROJECT_DIR/.env"
  echo "⚠️  IMPORTANT: Edit .env and add your API keys:"
  echo "   nano $PROJECT_DIR/.env"
fi

# Step 10: Create models directory
echo "[10/10] Creating models directory..."
mkdir -p "$PROJECT_DIR/models"

# Completion message
echo ""
echo "================================================"
echo "✅ Installation Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure API keys (REQUIRED for API-based tools):"
echo "   nano $PROJECT_DIR/.env"
echo ""
echo "2. Activate virtual environment:"
echo "   cd $PROJECT_DIR"
echo "   source ai-env/bin/activate"
echo ""
echo "3. Run AI CLI (interactive chat):"
echo "   python ai_cli.py"
echo ""
echo "4. Chat with a local model (optional, requires a GGUF model in models/):"
echo "   python local_llm.py"
echo "   python local_llm.py --list-models    # see what is available"
echo ""
echo "5. Quick info:"
echo "   neofetch"
echo ""
echo "📁 Project directory: $PROJECT_DIR"
echo "🐍 Virtual env: $PROJECT_DIR/ai-env"
echo "🤖 Models dir: $PROJECT_DIR/models"
echo ""
