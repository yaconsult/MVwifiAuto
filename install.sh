#!/bin/bash
# Install MV WiFi Auto as a user systemd service

set -e

echo "=== MV WiFi Auto Installer ==="

# Check prerequisites
echo "Checking prerequisites..."

# Check for NetworkManager
if ! command -v nmcli &> /dev/null; then
    echo "ERROR: NetworkManager (nmcli) not found. Install with: sudo dnf install NetworkManager"
    exit 1
fi

# Check for python3-dbus
if ! python3 -c "import dbus" 2>/dev/null; then
    echo "ERROR: python3-dbus not found. Install with: sudo dnf install python3-dbus"
    exit 1
fi

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "Prerequisites OK"

# Setup virtual environment with system site packages
echo "Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    uv venv --system-site-packages
fi

# Install dependencies and package
echo "Installing dependencies..."
uv sync

# Install the package in editable mode
echo "Installing mvwifi-auto..."
uv pip install -e .

# Check if installation worked
if ! uv run mvwifi-auto --help &>/dev/null; then
    echo "ERROR: Installation failed"
    exit 1
fi

echo "Package installed successfully"

# Install systemd user service
echo "Installing systemd user service..."
mkdir -p ~/.config/systemd/user
cp systemd/mvwifi-auto.service ~/.config/systemd/user/

# Get the actual path for ExecStart and update service file
BIN_PATH="$HOME/.local/bin"
mkdir -p "$BIN_PATH"

# Create wrapper script
WRAPPER="$BIN_PATH/mvwifi-auto"
cat > "$WRAPPER" << 'EOF'
#!/bin/bash
# Wrapper script to run mvwifi-auto from the project directory
cd "$(dirname "$(dirname "$(readlink -f "$0")")")"
exec uv run mvwifi-auto "$@"
EOF
chmod +x "$WRAPPER"

# Update service file to use the correct path
sed -i "s|%h/.local/bin/mvwifi-auto|$WRAPPER|g" ~/.config/systemd/user/mvwifi-auto.service

# Reload systemd
systemctl --user daemon-reload

echo ""
echo "=== Installation Complete ==="
echo ""
echo "To start the service:"
echo "  systemctl --user start mvwifi-auto"
echo ""
echo "To enable auto-start on login:"
echo "  systemctl --user enable mvwifi-auto"
echo ""
echo "To check status:"
echo "  systemctl --user status mvwifi-auto"
echo "  journalctl --user -u mvwifi-auto -f"
echo ""
echo "To run once manually (for testing):"
echo "  mvwifi-auto --once --verbose"
echo ""
