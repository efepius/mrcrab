#!/bin/bash
# Mr. Crab — Install Script
# Run as root on your Ubuntu VM: sudo bash install-service.sh

set -e

INSTALL_DIR="/opt/mrcrab"
SERVICE_USER="mrcrab"

echo "=== Mr. Crab Installation ==="

# 1. Install system dependencies
echo "[1/6] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv golang-go git

# 2. Create dedicated non-root user
echo "[2/6] Creating service user '$SERVICE_USER'..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -m -d "$INSTALL_DIR" -s /bin/bash "$SERVICE_USER"
fi

# 3. Copy project files
echo "[3/6] Copying project files to $INSTALL_DIR..."
rsync -a --exclude='.env' --exclude='data/' --exclude='.venv/' \
    "$(dirname "$0")/../" "$INSTALL_DIR/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# 4. Create Python virtualenv and install dependencies
echo "[4/6] Setting up Python environment..."
sudo -u "$SERVICE_USER" python3 -m venv "$INSTALL_DIR/.venv"
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --quiet \
    -r "$INSTALL_DIR/requirements.txt"

# 5. Create data directories
echo "[5/6] Creating data directories..."
sudo -u "$SERVICE_USER" mkdir -p \
    "$INSTALL_DIR/data/sessions" \
    "$INSTALL_DIR/data/uploads" \
    "$INSTALL_DIR/data/workspace"

# 6. Install and enable systemd service
echo "[6/6] Installing systemd service..."
cp "$INSTALL_DIR/systemd/claude-gateway.service" /etc/systemd/system/mrcrab.service
systemctl daemon-reload
systemctl enable mrcrab
systemctl restart mrcrab

echo ""
echo "=== Mr. Crab installed successfully! ==="
echo ""
echo "Next steps:"
echo "  1. Edit /opt/mrcrab/.env with your API keys"
echo "  2. Restart the service: systemctl restart mrcrab"
echo "  3. Check logs: journalctl -u mrcrab -f"
echo ""
systemctl status mrcrab --no-pager
