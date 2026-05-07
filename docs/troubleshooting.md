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
   cd ~/PycharmProjects/MVwifiAuto
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
   cd ~/PycharmProjects/MVwifiAuto
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

2. **Get gateway IP**:
   ```bash
   ip route show default
   # Should show gateway for cmvwifi connection
   ```

3. **Test portal acceptance manually**:
   ```bash
   GATEWAY=$(ip route | grep default | head -1 | awk '{print $3}')
   curl -X POST "http://${GATEWAY}/forms/guest_toued" \
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
cd ~/PycharmProjects/MVwifiAuto
uv run mvwifi-auto --daemon --interval 30 --verbose
```

### Run Tests

```bash
cd ~/PycharmProjects/MVwifiAuto

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
   cd ~/PycharmProjects/MVwifiAuto
   uv run mvwifi-auto --once --verbose 2>&1
   ```

5. **Environment**:
   - Fedora version
   - NetworkManager version (`nmcli --version`)
   - Python version (`python3 --version`)
