#!/bin/bash
# Mr. Crab — One-Shot Deploy Script
# Runs on your Ubuntu VM. Sets up everything from scratch.
#
# Usage:
#   ssh theboy@72.62.155.232
#   git clone <your-repo> ~/mrcrab && cd ~/mrcrab/claude-gateway
#   bash scripts/deploy.sh
#
# What this does:
#   1. Installs system dependencies (Python, Go)
#   2. Installs Ollama + pulls llama3.2-vision:11b (best free model)
#   3. Installs Mr. Crab to /opt/mrcrab
#   4. Creates .env from template
#   5. Installs and starts the systemd service

set -e

INSTALL_DIR="/opt/mrcrab"
SERVICE_USER="mrcrab"
MODEL="llama3.2-vision:11b"
FALLBACK_MODEL="llama3.1:8b"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
section() { echo ""; echo -e "${GREEN}══ $* ══${NC}"; }

echo ""
echo "  ╔═══════════════════════════════╗"
echo "  ║     🦀  Mr. Crab Deploy       ║"
echo "  ║   Free AI Bot — Llama Vision  ║"
echo "  ╚═══════════════════════════════╝"
echo ""

# Must run as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[!] Please run as root: sudo bash scripts/deploy.sh${NC}"
    exit 1
fi

SOURCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ─── STEP 1: System dependencies ──────────────────────────────────────────────
section "Step 1/5: System dependencies"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv golang-go git curl rsync
info "System packages installed"

# ─── STEP 2: Install Ollama ────────────────────────────────────────────────────
section "Step 2/5: Ollama + AI model"

if ! command -v ollama &>/dev/null; then
    info "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    info "Ollama already installed: $(ollama --version)"
fi

# Start service
systemctl enable ollama 2>/dev/null || true
systemctl start ollama 2>/dev/null || true
sleep 2

# Check RAM and pick best model
TOTAL_RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
info "Available RAM: ${TOTAL_RAM_GB}GB"

if [ "$TOTAL_RAM_GB" -ge 16 ]; then
    CHOSEN_MODEL="$MODEL"
    info "Enough RAM — using $MODEL (best, supports vision + images)"
else
    CHOSEN_MODEL="$FALLBACK_MODEL"
    warn "Less than 16GB RAM — using $FALLBACK_MODEL (still great, just no image support)"
fi

info "Downloading $CHOSEN_MODEL (this will take a few minutes)..."
ollama pull "$CHOSEN_MODEL"
info "Model ready: $CHOSEN_MODEL"

# ─── STEP 3: Install Mr. Crab ─────────────────────────────────────────────────
section "Step 3/5: Installing Mr. Crab"

# Create dedicated user
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -m -d "$INSTALL_DIR" -s /bin/bash "$SERVICE_USER"
    info "Created user: $SERVICE_USER"
fi

# Copy files
mkdir -p "$INSTALL_DIR"
rsync -a --exclude='.env' --exclude='data/' --exclude='.venv/' \
    "$SOURCE_DIR/" "$INSTALL_DIR/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
info "Files copied to $INSTALL_DIR"

# Create data directories
sudo -u "$SERVICE_USER" mkdir -p \
    "$INSTALL_DIR/data/sessions" \
    "$INSTALL_DIR/data/uploads" \
    "$INSTALL_DIR/data/workspace"
info "Data directories created"

# Python venv
sudo -u "$SERVICE_USER" python3 -m venv "$INSTALL_DIR/.venv"
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet \
    -r "$INSTALL_DIR/requirements.txt"
info "Python environment ready"

# ─── STEP 4: Configure .env ───────────────────────────────────────────────────
section "Step 4/5: Configuration"

ENV_FILE="$INSTALL_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    cp "$INSTALL_DIR/.env.example" "$ENV_FILE"

    # Set Ollama as the AI provider with chosen model
    sed -i "s|^AI_API_KEY=.*|AI_API_KEY=ollama|" "$ENV_FILE"
    sed -i "s|^AI_BASE_URL=.*|AI_BASE_URL=http://localhost:11434/v1|" "$ENV_FILE"
    sed -i "s|^AI_MODEL=.*|AI_MODEL=$CHOSEN_MODEL|" "$ENV_FILE"

    chown "$SERVICE_USER:$SERVICE_USER" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    info ".env created at $ENV_FILE"
    warn "Add your platform tokens to $ENV_FILE before starting the bot!"
else
    # Update model if .env already exists
    sed -i "s|^AI_MODEL=.*|AI_MODEL=$CHOSEN_MODEL|" "$ENV_FILE"
    info ".env already exists — model updated to $CHOSEN_MODEL"
fi

# ─── STEP 5: systemd service ──────────────────────────────────────────────────
section "Step 5/5: systemd service"

cat > /etc/systemd/system/mrcrab.service << EOF
[Unit]
Description=Mr. Crab — Claude AI Gateway Bot
After=network-online.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/.venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=mrcrab
MemoryMax=2G

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mrcrab
info "Service installed and enabled"

# ─── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "  ╔═══════════════════════════════════════════════╗"
echo "  ║   Mr. Crab installed successfully!            ║"
echo "  ║                                               ║"
echo "  ║   Model:  $CHOSEN_MODEL"
echo "  ║   Config: $ENV_FILE"
echo "  ║                                               ║"
echo "  ║   NEXT STEPS:                                 ║"
echo "  ║   1. Edit $ENV_FILE             ║"
echo "  ║      Add your TELEGRAM_BOT_TOKEN              ║"
echo "  ║      (get one free from @BotFather)           ║"
echo "  ║                                               ║"
echo "  ║   2. Start Mr. Crab:                          ║"
echo "  ║      systemctl start mrcrab                   ║"
echo "  ║                                               ║"
echo "  ║   3. Watch logs:                              ║"
echo "  ║      journalctl -u mrcrab -f                  ║"
echo "  ╚═══════════════════════════════════════════════╝"
echo ""
