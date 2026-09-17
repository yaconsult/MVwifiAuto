# MV WiFi Auto - Troubleshooting Guide

## Common Issues

### Service Won't Start

**Problem**: `systemctl --user start mvwifi-auto` fails

**Check**:
```bash
# Check service status
systemctl --user status mvwifi-auto

# Check for errors in logs
journalctl --user -u mvwifi-auto --since "5 minutes ago"
```

**Common Causes**:

1. **Missing dependencies**
   ```bash
   # Check if uv is installed
   which uv
   
   # Check if python3-dbus is installed
   python3 -c "import dbus; print('OK')"
   # If fails: sudo dnf install python3-dbus
   
   # Check if requests is available
   python3 -c "import requests; print('OK')"
   ```

2. **Virtual environment issues**
   ```bash
   # Reinstall from scratch
   cd ~/DevinProjects/MVwifiAuto
   rm -rf .venv
   uv venv --system-site-packages
   uv sync
   ```

3. **Wrong ExecStart path**
   ```bash
   # Check the wrapper script exists
   cat ~/.local/bin/mvwifi-auto
   
   # Update service file if needed
   systemctl --user daemon-reload
   ```

### D-Bus Permission Errors

**Problem**: `AccessDenied: Sender is not authorized` when running as systemd user service

**Cause**: Systemd user service doesn't have D-Bus permissions to access NetworkManager

**Solution**:

**Quick workaround** (for testing):
```bash
# Stop systemd service
systemctl --user stop mvwifi-auto

# Run in user session instead (avoids permission issues)
mvwifi-auto --daemon &
```

**Proper fix** (recommended):

Create a polkit rule to allow your user to access NetworkManager:

```bash
sudo tee /etc/polkit-1/rules.d/50-mvwifi-auto.rules << 'EOF'
/* Allow mvwifi-auto user service to access NetworkManager */
polkit.addRule(function(action, subject) {
    if (action.id.indexOf("org.freedesktop.NetworkManager.") == 0 &&
        subject.user == "USERNAME") {
        return polkit.Result.YES;
    }
});
EOF
# Replace USERNAME with your actual username
```

Then reload and restart:
```bash
sudo systemctl restart polkit
systemctl --user restart mvwifi-auto
```

**Verify the fix:**
```bash
mvwifi-auto --once --verbose
# Should show: "Current state: ssid='cmvwifi', internet=True"
```

### Not Connecting to cmvwifi

**Problem**: Service running but not connecting when cmvwifi is available

**Diagnosis Steps**:

1. **Check if cmvwifi is visible**:
   ```bash
   nmcli device wifi list | grep cmvwifi
   ```

2. **Run manual test with verbose output**:
   ```bash
   cd ~/DevinProjects/MVwifiAuto
   uv run mvwifi-auto --once --verbose
   ```

3. **Check NetworkManager can connect**:
   ```bash
   # Try manual connection
   nmcli device wifi connect cmvwifi
   
   # If successful, captive portal should appear in browser
   ```

4. **Test captive portal detection**:
   ```bash
   curl -v http://detectportal.firefox.com/canonical.html
   # Should redirect if behind portal
   ```

**Common Causes**:

- **cmvwifi not in range** - Check signal strength
- **Portal detection failing** - May need to adjust detection logic
- **Connection timeout** - Increase timeout in code

### Interferes with dd-wrt Connection

**Problem**: Service disrupts existing dd-wrt connection

**Expected Behavior**: Service should NOT interfere with dd-wrt

**Verification**:
```bash
# When on dd-wrt, service should log:
# "Current state: ssid=dd-wrt, internet=True"
# And take no action

journalctl --user -u mvwifi-auto -f
```

**If interference occurs**:
1. Check decision logic in logs
2. Verify dd-wrt is in preferred networks list
3. Check if internet detection is working

### Captive Portal Not Accepted

**Problem**: Connected to cmvwifi but no internet (portal not accepted)

**Diagnosis**:

1. **Check if connected to cmvwifi**:
   ```bash
   nmcli connection show --active | grep cmvwifi
   ```

2. **Get portal host**:
   ```bash
   # The portal host is extracted from the redirect URL, not the gateway
   curl -v --max-redirs 5 http://1.1.1.1/ 2>&1 | grep "Location:"
   # Or follow redirects and check the final URL:
   curl -L -o /dev/null -w "%{url_effective}\n" http://1.1.1.1/
   ```

3. **Test portal acceptance manually**:
   ```bash
   # Extract the host from the redirect URL (e.g. 10.64.2.21:9997)
   PORTAL_HOST="10.64.2.21:9997"
   curl -X POST "http://${PORTAL_HOST}/forms/guest_toued" \
     -d "origurl=http://www.google.com" \
     -d "ok=Accept and Continue" \
     -v
   ```

4. **Check portal detection**:
   ```bash
   curl -I http://detectportal.firefox.com/canonical.html
   ```

**If manual works but auto doesn't**:
- Check logs for portal handling errors
- May need to increase delays/timeouts
- Gateway detection might be failing

### Service Stops After Suspend/Resume

**Problem**: Service doesn't resume after laptop wakes from sleep

**Check systemd configuration**:
```bash
# Check if service is still enabled
systemctl --user is-enabled mvwifi-auto

# Check last start time
systemctl --user status mvwifi-auto | grep "Active:"
```

**Solution**:
The service has `Restart=always` which should handle this. If not:

1. Check systemd user instance is running:
   ```bash
   systemctl --user status
   ```

2. Consider adding to systemd user linger:
   ```bash
   # Enable lingering (allows user services without login)
   sudo loginctl enable-linger $USER
   ```

## Debug Mode

### Enable Verbose Logging

Edit the service to add `--verbose`:
```bash
# Edit service file
systemctl --user edit mvwifi-auto

# Add to [Service] section:
# ExecStart=
# ExecStart=%h/.local/bin/mvwifi-auto --daemon --interval 60 --verbose
```

Or run manually:
```bash
cd ~/DevinProjects/MVwifiAuto
uv run mvwifi-auto --daemon --interval 30 --verbose
```

### Run Tests

```bash
cd ~/DevinProjects/MVwifiAuto

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mvwifi_auto --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_controller.py -v
```

### Manual Component Testing

**Test NetworkManager interface**:
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from mvwifi_auto.network_manager import get_connection_info, find_network

# Check current connection
info = get_connection_info()
print(f"Current: {info}")

# Scan for cmvwifi
result = find_network("cmvwifi")
print(f"cmvwifi found: {result}")
EOF
```

**Test captive portal**:
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
from mvwifi_auto.captive_portal import (
    detect_captive_portal, 
    get_default_gateway,
    verify_internet_connectivity
)

# Detect portal
is_captive, redirect = detect_captive_portal()
print(f"Captive: {is_captive}, Redirect: {redirect}")

# Get gateway
gateway = get_default_gateway()
print(f"Gateway: {gateway}")

# Check internet
has_internet = verify_internet_connectivity()
print(f"Internet: {has_internet}")
EOF
```

## Log Analysis

### Common Log Messages

| Message | Meaning | Action |
|---------|---------|--------|
| `Current state: ssid=dd-wrt, internet=True` | On home WiFi | Normal, no action |
| `Decision: none - Already connected to preferred` | Correctly idle | None needed |
| `Scanning for WiFi networks...` | Starting scan | Normal operation |
| `Decision: connect_cmvwifi` | Will connect to public | Wait for connection |
| `Connecting to cmvwifi...` | Starting connection | Should complete soon |
| `Captive portal accept: 200` | Portal accepted | Should have internet |
| `Successfully connected with internet access` | Success | None needed |
| `NetworkManager error: ...` | D-Bus/scan error | Check NetworkManager |
| `Scan failed: AccessDenied` | Permission issue | Check user permissions |

### Getting More Logs

```bash
# Follow logs in real-time
journalctl --user -u mvwifi-auto -f

# Get last 100 lines
journalctl --user -u mvwifi-auto -n 100

# Get logs since last boot
journalctl --user -u mvwifi-auto --since "today"

# Get logs with specific time range
journalctl --user -u mvwifi-auto --since "2026-05-07 10:00" --until "2026-05-07 11:00"
```

## Reporting Issues

When reporting issues, include:

1. **Service status**:
   ```bash
   systemctl --user status mvwifi-auto
   ```

2. **Recent logs**:
   ```bash
   journalctl --user -u mvwifi-auto --since "1 hour ago"
   ```

3. **Network status**:
   ```bash
   nmcli device status
   nmcli connection show --active
   ```

4. **Test output**:
   ```bash
   cd ~/DevinProjects/MVwifiAuto
   uv run mvwifi-auto --once --verbose 2>&1
   ```

5. **Environment**:
   - Fedora version
   - NetworkManager version (`nmcli --version`)
   - Python version (`python3 --version`)

## Android/Termux Issues

### WiFi Near profile never activates

**Problem**: The `cmvwifi Auto Connect` profile is enabled (green
dot) but never turns green even when cmvwifi is visible in the
WiFi scan list.

**Cause**: The imported profile may have wrong WiFi Near arg order.
Tasker normalizes imported args by type, not by index — if an Int
is sent where a Str is expected, the value ends up in the wrong
position. In our case, `Int 0` for arg1 became `Str "0"` for the
MAC field, meaning the profile looked for a network with MAC
address "0" which never matches.

**Fix**: Regenerate and re-import the Tasker XML:

```bash
cd ~/DevinProjects/MVwifiAuto
uv run python -m mvwifi_auto.tasker_gen --termux -o android/MVwifiAuto-Termux.prj.xml
adb push android/MVwifiAuto-Termux.prj.xml /sdcard/Tasker/projects/
```

Then import the project in Tasker (long-press bottom nav bar →
Import Project → `MVwifiAuto-Termux`).

**Verify**: After importing, the profile should activate when
near the target SSID. You can test at home by creating a WiFi
Near profile for a visible network (e.g. `dd-wrt`) — it should
turn green within 60 seconds.

### Delay between "Portal handling complete" and working internet

**Problem**: The "Portal handling complete" toast appears but the
phone doesn't show a working WiFi connection for several minutes.

**Cause**: This is normal. After our script accepts the portal
terms, Android runs its own connectivity validation
(`connectivitycheck.gstatic.com/generate_204`) before switching
the default route from cellular to WiFi. Android batches these
checks — 1-3 minutes is normal, especially when cellular data
is active and being preferred.

**Fix**: None needed — this is OS behavior. If faster switchover
is needed, disable cellular data during the run (Tasker Settings
→ Mobile Data toggle) or use `svc data disable` with root, but
both trade convenience for speed.

### HTTP requests timing out with cellular ON

**Problem**: `mvwifi-android --once --verbose` hangs for ~40 seconds
per request and never completes.

**Cause**: Source IP binding alone doesn't bypass Android's policy
routing. The kernel still routes packets over cellular even with the
correct wlan0 source IP.

**Fix**: The code uses `SO_BINDTODEVICE` (socket option 25) for
kernel-level interface binding. This should work from Termux without
root. If it doesn't, verify with:

```bash
python scripts/test_bindtodevice.py
```

If `SO_BINDTODEVICE` reports "PERMISSION DENIED", your device may need
root or `CAP_NET_RAW`.

### "Could not determine IPv4 address for interface 'wlan0'"

**Cause**: The WiFi interface may be `wlan1` on some Pixel devices, or
WiFi isn't connected yet (no IP assigned).

**Fix**: The script auto-detects the interface. If that fails, find it
manually:

```bash
python scripts/detect_interface.py
```

Note: `ip addr` does not work from Termux (Android blocks netlink
sockets). The ioctl-based detection in the script works fine.

### `ip addr` returns "cannot bind netlink socket permission denied"

**Cause**: Android blocks netlink sockets for non-system apps. This is
expected — Termux cannot use `ip addr`.

**Fix**: Use the ioctl-based detection instead. The diagnostic script
`scripts/detect_interface.py` uses `SIOCGIFADDR` ioctl which works from
Termux.

### Debugging on the phone

Write logs to a file for transfer:

```bash
# To Termux home (no permissions needed)
mvwifi-android --once --verbose --log-file ~/mvwifi.log

# To shared storage (requires termux-setup-storage first)
mvwifi-android --once --verbose --log-file ~/storage/shared/mvwifi.log
```

On success, the log file is **deleted automatically** — it only
exists if the run failed. This makes it easy to check for problems:
if the file exists, something went wrong.

The Tasker wrapper script writes to
`~/storage/shared/mvwifi_tasker.log` by default.

Transfer via `adb pull`, Google Drive, or `cat` and copy from the
Termux screen.
