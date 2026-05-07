# MV WiFi Auto

Automatically connects to Mountain View public WiFi (`cmvwifi`) when in range and handles the captive portal acceptance. Designed as a user systemd service that runs on Fedora (and other Linux systems with NetworkManager).

## How It Works

1. **Scanning**: Every 60 seconds, the service scans for available WiFi networks
2. **Priority Logic**: 
   - If already connected to `dd-wrt` (home WiFi) with internet → does nothing
   - If already connected to `cmvwifi` with internet → does nothing
   - If `dd-wrt` is available but not connected → lets NetworkManager autoconnect (which it should already do)
   - If only `cmvwifi` is available → connects and accepts the captive portal terms
   - If neither → does nothing (waiting for you to be in range)

## Installation

### Prerequisites

- Fedora (or any Linux with NetworkManager)
- Python 3.11+
- `uv` for Python package management
- `nmcli` (usually included with NetworkManager)

### Install

```bash
# Clone or copy this project
cd ~/PycharmProjects/MVwifiAuto

# Install dependencies
uv sync

# Install the package in user mode
uv pip install -e .

# Or install directly to user bin
mkdir -p ~/.local/bin
cp -r src/mvwifi_auto ~/.local/lib/python3.*/site-packages/ 2>/dev/null || true
# Or use: pip install --user -e .
```

### Install Systemd Service

```bash
# Create systemd user directory if needed
mkdir -p ~/.config/systemd/user

# Copy service file
cp systemd/mvwifi-auto.service ~/.config/systemd/user/

# Reload systemd daemon
systemctl --user daemon-reload

# Enable and start service
systemctl --user enable mvwifi-auto.service
systemctl --user start mvwifi-auto.service

# Check status
systemctl --user status mvwifi-auto.service

# View logs
journalctl --user -u mvwifi-auto -f
```

## Usage

### As a Service (Recommended)

The service runs automatically in the background, checking every 60 seconds.

```bash
# Start/stop/restart
systemctl --user start mvwifi-auto
systemctl --user stop mvwifi-auto
systemctl --user restart mvwifi-auto

# View logs
journalctl --user -u mvwifi-auto -f
```

### Manual/One-Shot Mode

Run once manually (useful for testing):

```bash
# Run once and exit
mvwifi-auto --once

# Verbose output
mvwifi-auto --once --verbose

# Daemon mode in foreground
mvwifi-auto --daemon --interval 60
```

### Testing Without Connecting

You can test the logic without actually connecting:

```bash
# Just check current state (verbose)
mvwifi-auto --once -v
```

## Configuration

Edit the constants in `src/mvwifi_auto/controller.py` to customize:

```python
PREFERRED_NETWORKS = ["dd-wrt"]  # Your home WiFi
PUBLIC_NETWORK = "cmvwifi"       # Mountain View public WiFi
SCAN_TIMEOUT = 15.0              # Seconds to wait for WiFi scan
```

Or pass custom settings via environment variables (not yet implemented - PR welcome!).

## Development

```bash
# Setup dev environment
uv sync

# Run linting
ruff check src/
ruff format src/

# Type checking
mypy src/

# Run tests (when added)
pytest
```

## How the Captive Portal Works

Based on the [micropython captive portal implementation](https://github.com/lpinard/WeatherClock-micropython), the Mountain View WiFi captive portal:

1. Redirects all HTTP requests to a login page
2. Requires POST to `/forms/guest_toued` with:
   - `origurl`: The original URL you tried to visit
   - `ok`: Button value ("Accept and Continue")

The service handles this automatically after connecting to `cmvwifi`.

## Troubleshooting

### Service won't start

```bash
# Check for errors
systemctl --user status mvwifi-auto
journalctl --user -u mvwifi-auto --since "1 hour ago"

# Check if mvwifi-auto is in PATH
which mvwifi-auto
# If not, add ~/.local/bin to your PATH
```

### Not connecting to cmvwifi

```bash
# Run manually with verbose output
mvwifi-auto --once --verbose

# Check if NetworkManager can see the network
nmcli device wifi list | grep cmvwifi

# Test captive portal manually
curl -v http://detectportal.firefox.com/canonical.html
```

### D-Bus permission errors

Make sure your user has access to NetworkManager D-Bus:

```bash
# Check if you can access nm
nmcli general status

# If that works, D-Bus should work too
```

## Files

- `src/mvwifi_auto/controller.py` - Main logic and decision engine
- `src/mvwifi_auto/network_manager.py` - NetworkManager D-Bus interface
- `src/mvwifi_auto/captive_portal.py` - Captive portal handling
- `systemd/mvwifi-auto.service` - User systemd service unit

## License

MIT License - See LICENSE file
