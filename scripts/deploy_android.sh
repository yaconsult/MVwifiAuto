#!/bin/bash
# PC-side deployment for MVwifiAuto Android integration.
#
# Run from the repo root with the phone connected via USB:
#   ./scripts/deploy_android.sh
#
# This script:
#   1. Pushes the Tasker XML to the phone
#   2. Creates the Termux wrapper script via adb
#   3. Enables allow-external-apps in termux.properties via adb
#   4. Grants RUN_COMMAND permission to Tasker via adb
#   5. Verifies the setup
#
# Requires: adb with the phone connected and USB debugging enabled.
# Requires: root (Magisk) for accessing Termux's private files.

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TASKER_XML="$REPO_DIR/android/MVwifiAuto-Termux.prj.xml"
TERMUX_HOME="/data/data/com.termux/files/home"
TASKER_DIR="$TERMUX_HOME/.termux/tasker"
PROPS_FILE="$TERMUX_HOME/.termux/termux.properties"

# Check adb
if ! command -v adb >/dev/null 2>&1; then
    echo "ERROR: adb not found. Install android-tools or platform-tools."
    exit 1
fi

# Check device connected
if ! adb devices | grep -q "device$"; then
    echo "ERROR: No device connected. Enable USB debugging and authorize the connection."
    adb devices
    exit 1
fi

echo "=== MVwifiAuto Android Deployment ==="
echo ""

# Check root
if ! adb shell "su -c 'id'" 2>/dev/null | grep -q "uid=0"; then
    echo "ERROR: Root not available. Enable shell access in Magisk settings."
    exit 1
fi
echo "Root: OK"
echo ""

# --- Step 1: Push Tasker XML ---
echo "[1/5] Pushing Tasker XML..."
if [ ! -f "$TASKER_XML" ]; then
    echo "  Tasker XML not found. Generating..."
    cd "$REPO_DIR"
    uv run python -m mvwifi_auto.tasker_gen --termux -o "$TASKER_XML"
fi
adb shell "mkdir -p /sdcard/Tasker/projects/" 2>/dev/null || true
adb push "$TASKER_XML" /sdcard/Tasker/projects/MVwifiAuto-Termux.prj.xml
echo "  Pushed to /sdcard/Tasker/projects/MVwifiAuto-Termux.prj.xml"
echo ""

# --- Step 2: Create wrapper script ---
echo "[2/5] Creating Termux wrapper script..."
adb shell "su -c 'mkdir -p $TASKER_DIR'"
adb shell "su -c 'cat > $TASKER_DIR/mvwifi_portal << \"ENDOFSCRIPT\"
#!/data/data/com.termux/files/usr/bin/sh
exec /data/data/com.termux/files/usr/bin/mvwifi-android --once
ENDOFSCRIPT'"
adb shell "su -c 'chmod 755 $TASKER_DIR/mvwifi_portal'"
echo "  Created: $TASKER_DIR/mvwifi_portal"
echo ""

# --- Step 3: Enable allow-external-apps ---
echo "[3/5] Configuring termux.properties..."
adb shell "su -c 'mkdir -p $TERMUX_HOME/.termux'"
# Check if already set
ALREADY_SET=$(adb shell "su -c 'grep -c \"^allow-external-apps\" $PROPS_FILE 2>/dev/null'" 2>/dev/null || echo "0")
if [ "$ALREADY_SET" = "0" ]; then
    adb shell "su -c 'echo \"allow-external-apps = true\" >> $PROPS_FILE'"
    echo "  Added allow-external-apps = true"
else
    echo "  allow-external-apps already set"
fi
echo ""

# --- Step 4: Grant RUN_COMMAND permission ---
echo "[4/5] Granting RUN_COMMAND permission to Tasker..."
# Try granting via pm (may fail silently if already granted)
adb shell "pm grant net.dinglisch.android.taskerm com.termux.permission.RUN_COMMAND" 2>/dev/null || true
# Verify
PERM_GRANTED=$(adb shell "dumpsys package net.dinglisch.android.taskerm 2>/dev/null | grep 'RUN_COMMAND' | grep -c 'granted=true'" 2>/dev/null || echo "0")
if [ "$PERM_GRANTED" != "0" ]; then
    echo "  Permission granted"
else
    echo "  WARNING: Could not verify permission. Grant manually:"
    echo "    Android Settings -> Apps -> Tasker -> Permissions"
    echo "    -> Additional permissions -> Run commands in Termux environment"
fi
echo ""

# --- Step 5: Verify ---
echo "[5/5] Verifying deployment..."
echo "  Wrapper script:"
adb shell "su -c 'ls -la $TASKER_DIR/mvwifi_portal'" 2>&1 | sed 's/^/    /'
echo "  Script contents:"
adb shell "su -c 'cat $TASKER_DIR/mvwifi_portal'" 2>&1 | sed 's/^/    /'
echo "  mvwifi-android:"
adb shell "su -c 'ls -la /data/data/com.termux/files/usr/bin/mvwifi-android'" 2>&1 | sed 's/^/    /'
echo "  Tasker XML on phone:"
adb shell "ls -la /sdcard/Tasker/projects/MVwifiAuto-Termux.prj.xml" 2>&1 | sed 's/^/    /'
echo ""

echo "=== Deployment complete! ==="
echo ""
echo "Next steps:"
echo "  1. Force-close Termux (Settings -> Apps -> Termux -> Force Stop)"
echo "     and reopen it for termux.properties changes to take effect."
echo "  2. In Tasker: long-press bottom nav bar -> Import Project"
echo "     -> select MVwifiAuto-Termux"
echo "  3. Test: run the 'ConnectAndRun' task in Tasker"
echo "  4. Enable the WiFi Near profile (green dot in PROFILES tab)"
