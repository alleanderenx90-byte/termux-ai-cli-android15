#!/usr/bin/env bash
set -e

# Termux AI CLI - Full Automated Installation for Android 15
# One-command setup for OpenAI, Anthropic, Hugging Face, local LLMs

echo "================================================"
echo "Termux AI CLI - Full Automated Setup"
echo "Android 15 Edition"
echo "================================================"
echo ""

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
echo "[4/10] Creating project directories..."
PROJECT_DIR="$HOME/ai-projects"
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
pip install -y \
  openai \
  anthropic \
  transformers \
  huggingface_hub \
  torch \
  llama-cpp-python \
  python-dotenv \
  requests \
  pydantic \
  typer \
  rich

# Step 8: Clone repo and copy scripts
echo "[8/10] Setting up AI CLI scripts..."
if [ ! -d "$PROJECT_DIR/termux-ai-cli" ]; then
  git clone https://github.com/alleanderenx90-byte/termux-ai-cli-android15 termux-ai-cli
fi
cp -v termux-ai-cli/scripts/* . 2>/dev/null || true

# Step 9: Create .env file
echo "[9/10] Creating .env configuration file..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
  cat > "$PROJECT_DIR/.env" << 'EOF'
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic Configuration
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Hugging Face Configuration
HF_TOKEN=your_huggingface_token_here

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
echo "4. Test local LLM (optional, requires GGUF model):"
echo "   python local_llm_test.py"
echo ""
echo "5. Quick info:"
echo "   neofetch"
echo ""
echo "📁 Project directory: $PROJECT_DIR"
echo "🐍 Virtual env: $PROJECT_DIR/ai-env"
echo "🤖 Models dir: $PROJECT_DIR/models"
echo ""
