#!/data/data/com.termux/files/usr/bin/sh
# Termux-side setup for MVwifiAuto Android integration.
#
# Run this inside Termux after cloning the repo:
#   cd ~/MVwifiAuto
#   sh scripts/termux_setup.sh
#
# This script:
#   1. Creates the wrapper script for Termux:Tasker
#   2. Enables allow-external-apps in termux.properties
#   3. Installs the Python package if not already installed
#   4. Prints next steps for Tasker setup

set -e

PREFIX="/data/data/com.termux/files/usr"
HOME_DIR="/data/data/com.termux/files/home"
TASKER_DIR="$HOME_DIR/.termux/tasker"
PROPS_FILE="$HOME_DIR/.termux/termux.properties"

echo "=== MVwifiAuto Termux Setup ==="
echo ""

# --- Step 1: Install Python package ---
echo "[1/4] Checking mvwifi-android installation..."
if command -v mvwifi-android >/dev/null 2>&1; then
    echo "  mvwifi-android already installed: $(which mvwifi-android)"
else
    echo "  Installing mvwifi-auto package..."
    if [ ! -f "$HOME_DIR/MVwifiAuto/pyproject.toml" ]; then
        echo "  ERROR: ~/MVwifiAuto not found. Clone the repo first:"
        echo "    git clone https://github.com/yaconsult/MVwifiAuto.git ~/MVwifiAuto"
        exit 1
    fi
    cd "$HOME_DIR/MVwifiAuto"
    pip install -e .
    echo "  Installed: $(which mvwifi-android)"
fi
echo ""

# --- Step 2: Create wrapper script ---
echo "[2/4] Creating wrapper script for Termux:Tasker..."
mkdir -p "$TASKER_DIR"
cat > "$TASKER_DIR/mvwifi_portal" << 'WRAPPER_EOF'
#!/data/data/com.termux/files/usr/bin/sh
exec /data/data/com.termux/files/usr/bin/mvwifi-android --once --verbose --log-file /data/data/com.termux/files/home/storage/shared/mvwifi_tasker.log
WRAPPER_EOF
chmod 755 "$TASKER_DIR/mvwifi_portal"
echo "  Created: $TASKER_DIR/mvwifi_portal"
echo ""

# --- Step 3: Enable allow-external-apps ---
echo "[3/4] Configuring termux.properties..."
mkdir -p "$HOME_DIR/.termux"
if [ -f "$PROPS_FILE" ]; then
    if grep -q "^allow-external-apps" "$PROPS_FILE"; then
        echo "  allow-external-apps already set"
    else
        echo "allow-external-apps = true" >> "$PROPS_FILE"
        echo "  Added allow-external-apps = true"
    fi
else
    echo "allow-external-apps = true" > "$PROPS_FILE"
    echo "  Created $PROPS_FILE with allow-external-apps = true"
fi

# Reload Termux settings if the command exists
if command -v termux-reload-settings >/dev/null 2>&1; then
    termux-reload-settings
    echo "  Reloaded Termux settings"
fi
echo ""

# --- Step 4: Verify ---
echo "[4/4] Verifying setup..."
echo "  Wrapper script:"
ls -la "$TASKER_DIR/mvwifi_portal" 2>&1 | sed 's/^/    /'
echo "  mvwifi-android:"
ls -la "$PREFIX/bin/mvwifi-android" 2>&1 | sed 's/^/    /'
echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Grant RUN_COMMAND permission to Tasker:"
echo "     Android Settings -> Apps -> Tasker -> Permissions"
echo "     -> Additional permissions -> Run commands in Termux environment"
echo ""
echo "  2. Import the Tasker project:"
echo "     From your PC: adb push android/MVwifiAuto-Termux.prj.xml /sdcard/Tasker/projects/"
echo "     In Tasker: long-press bottom nav -> Import Project -> MVwifiAuto-Termux"
echo ""
echo "  3. Test: run the 'ConnectAndRun' task in Tasker"
