#!/bin/bash
# Mr. Crab — Ollama Model Installer
# Run on your Ubuntu VM: bash scripts/install-ollama.sh
#
# This installs Ollama and pulls the best free AI model for your hardware.
# Completely free — no API key, no account, runs 100% on your server.

set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   Mr. Crab — Ollama Setup            ║"
echo "║   Free AI, runs on your own server   ║"
echo "╚══════════════════════════════════════╝"
echo ""

# --- Detect available RAM ---
TOTAL_RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
echo "[info] Detected RAM: ${TOTAL_RAM_GB}GB"

# --- Detect GPU ---
HAS_GPU=false
if command -v nvidia-smi &>/dev/null; then
    GPU_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 || echo "0")
    GPU_VRAM_GB=$((GPU_VRAM / 1024))
    echo "[info] Detected NVIDIA GPU: ${GPU_VRAM_GB}GB VRAM"
    HAS_GPU=true
else
    echo "[info] No GPU detected — will use CPU inference"
fi

# --- Pick best model based on hardware ---
if [ "$HAS_GPU" = true ] && [ "$GPU_VRAM_GB" -ge 40 ]; then
    MODEL="llama3.1:70b-instruct-q4_K_M"
    MODEL_DESC="Llama 3.1 70B (quantized) — GPT-4 level, 40GB+ VRAM"
elif [ "$HAS_GPU" = true ] && [ "$GPU_VRAM_GB" -ge 16 ]; then
    MODEL="llama3.2-vision:11b"
    MODEL_DESC="Llama 3.2 Vision 11B — supports images, 16GB+ VRAM"
elif [ "$HAS_GPU" = true ] && [ "$GPU_VRAM_GB" -ge 8 ]; then
    MODEL="llama3.1:8b"
    MODEL_DESC="Llama 3.1 8B — fast, good quality, 8GB+ VRAM"
elif [ "$TOTAL_RAM_GB" -ge 32 ]; then
    MODEL="llama3.1:8b"
    MODEL_DESC="Llama 3.1 8B — runs on CPU with 32GB+ RAM"
elif [ "$TOTAL_RAM_GB" -ge 16 ]; then
    MODEL="llama3.2:3b"
    MODEL_DESC="Llama 3.2 3B — lightweight, runs on 16GB RAM"
else
    MODEL="llama3.2:1b"
    MODEL_DESC="Llama 3.2 1B — minimal hardware, basic capability"
fi

echo "[info] Selected model: $MODEL_DESC"
echo ""

# --- Install Ollama ---
if command -v ollama &>/dev/null; then
    echo "[✓] Ollama already installed: $(ollama --version)"
else
    echo "[1/3] Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "[✓] Ollama installed"
fi

# --- Start Ollama service ---
echo "[2/3] Starting Ollama service..."
if systemctl is-active --quiet ollama 2>/dev/null; then
    echo "[✓] Ollama service already running"
else
    systemctl enable ollama 2>/dev/null || true
    systemctl start ollama 2>/dev/null || ollama serve &
    sleep 3
    echo "[✓] Ollama service started"
fi

# --- Pull model ---
echo "[3/3] Downloading model: $MODEL"
echo "      (This may take a while depending on your connection)"
echo ""
ollama pull "$MODEL"
echo ""
echo "[✓] Model downloaded: $MODEL"

# --- Also pull a vision model if we only got a text model ---
if [[ "$MODEL" != *"vision"* ]] && [ "$HAS_GPU" = true ] && [ "$GPU_VRAM_GB" -ge 8 ]; then
    echo ""
    echo "[+] Also pulling vision model for image support..."
    ollama pull llama3.2-vision:11b 2>/dev/null || echo "    (skipped — not enough VRAM)"
fi

# --- Update .env ---
ENV_FILE="$(dirname "$0")/../.env"
if [ -f "$ENV_FILE" ]; then
    echo ""
    echo "[✓] Updating .env to use Ollama..."
    sed -i 's|^AI_API_KEY=.*|AI_API_KEY=ollama|' "$ENV_FILE"
    sed -i 's|^AI_BASE_URL=.*|AI_BASE_URL=http://localhost:11434/v1|' "$ENV_FILE"
    sed -i "s|^AI_MODEL=.*|AI_MODEL=$MODEL|" "$ENV_FILE"
    echo "[✓] .env updated"
else
    echo ""
    echo "[!] No .env found. Add these lines manually:"
    echo ""
    echo "    AI_API_KEY=ollama"
    echo "    AI_BASE_URL=http://localhost:11434/v1"
    echo "    AI_MODEL=$MODEL"
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Ollama setup complete!                 ║"
echo "║                                          ║"
echo "║   Model: $MODEL"
echo "║   API:   http://localhost:11434/v1       ║"
echo "║                                          ║"
echo "║   Test it:                               ║"
echo "║   ollama run $MODEL 'hello'    ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Restart Mr. Crab to apply: systemctl restart mrcrab"
