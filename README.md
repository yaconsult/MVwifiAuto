# MV WiFi Auto

Automatically connects to Mountain View's citywide community WiFi (`cmvwifi`) when in range and handles the captive portal acceptance. Designed as a user systemd service that runs on Fedora (and other Linux systems with NetworkManager).

The `cmvwifi` network is available at multiple locations throughout Mountain View, including the Mountain View Public Library, Shoreline Park, and various cafes and public spaces. See the [City of Mountain View WiFi page](https://www.mountainview.gov/city-hall/it/wifi) for coverage details.

## How It Works

1. **Scanning**: Every 60 seconds, the service scans for available WiFi networks
2. **Priority Logic**: 
   - If already connected to `dd-wrt` (home WiFi) with internet → does nothing
   - If already connected to `cmvwifi` with internet → does nothing
   - If `dd-wrt` is available but not connected → lets NetworkManager autoconnect (which it should already do)
   - If only `cmvwifi` is available → connects and accepts the captive portal terms
   - If neither → does nothing (waiting for you to be in range)

## Installation

### Quick Install (Recommended)

Run the install script that automates everything:

```bash
cd ~/DevinProjects/MVwifiAuto
./install.sh
```

Then start the service:
```bash
systemctl --user start mvwifi-auto
systemctl --user enable mvwifi-auto  # Auto-start on login
journalctl --user -u mvwifi-auto -f  # Watch logs
```

### Prerequisites

- Fedora (or any Linux with NetworkManager)
- Python 3.11+
- `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- `python3-dbus`: `sudo dnf install python3-dbus` (or `apt` on Debian/Ubuntu)
- `nmcli`: included with NetworkManager

### Manual Install (Alternative)

If you prefer not to use `install.sh`:

```bash
cd ~/DevinProjects/MVwifiAuto

# Setup venv with system site packages
uv venv --system-site-packages
uv sync
uv pip install -e .

# Install systemd service
mkdir -p ~/.config/systemd/user
cp systemd/mvwifi-auto.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable mvwifi-auto.service
systemctl --user start mvwifi-auto.service
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

### Suspend/Resume Handling

After sleep/hibernate, the captive portal session may expire. Enable the resume service to automatically reconnect:

```bash
# Enable resume check (runs once after waking)
systemctl --user enable mvwifi-auto-resume

# To check resume service logs
journalctl --user -u mvwifi-auto-resume -f
```

The resume service waits 5 seconds after waking, then runs a connectivity check.

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

### Other Networks

**Preferred networks** (like `dd-wrt`) and **other saved networks** (like `Pixel_6a`) are handled automatically by NetworkManager:

- **At home**: NetworkManager connects to `dd-wrt` or `dd-wrt_5G` automatically (if saved)
- **In the car**: NetworkManager connects to `Pixel_6a` hotspot automatically (if saved)
- **At the library, Shoreline Park, cafes, etc.**: Our service connects to `cmvwifi` and handles the captive portal

The service only intervenes for `cmvwifi`. All other networks are left to NetworkManager.

## Development

```bash
# Setup dev environment
uv sync

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=mvwifi_auto

# Run linting
uv run ruff check src/
uv run ruff format src/

# Type checking
uv run mypy src/
```

## How the Captive Portal Works

Based on the [micropython captive portal implementation](https://github.com/lpinard/WeatherClock-micropython), the Mountain View WiFi captive portal:

1. Redirects all HTTP requests to a login page
2. The portal host (IP:port) is extracted from the redirect URL — it may differ from the default gateway
3. Requires POST to `/forms/guest_toued` with:
   - `origurl`: The original URL you tried to visit
   - `ok`: Button value ("Accept and Continue")

The service handles this automatically after connecting to `cmvwifi`.

## Android Support

Two approaches are available for Android:

### Termux + Python (Recommended)

Runs the same Python portal-handling code as the laptop, with HTTP
traffic bound to the WiFi interface via `SO_BINDTODEVICE` to bypass
Android's cellular-preferred policy routing. Verified working with
cellular data enabled.

The flow: Tasker detects cmvwifi via WiFi Near → connects via Tasker
Settings → waits for DHCP → triggers `mvwifi-android` via the
Termux:Tasker plugin → Python binds to wlan0, detects the portal,
accepts terms, and verifies internet. On success, no log file is
left; on failure, `~/storage/shared/mvwifi_tasker.log` contains the
diagnostic output.

See [docs/android-termux-setup.md](docs/android-termux-setup.md)
for setup instructions, or run `scripts/deploy_android.sh` with the
phone connected via USB for one-command deployment.

### Tasker (Alternative)

Uses Tasker's WiFi Near profile for detection and HTTP Request actions
for portal handling. Does not work on Android 16 due to policy routing
(see [docs/android-devlog.md](docs/android-devlog.md) for details).
The Tasker XML is generated from testable Python code via
`tasker_gen.py`. See
[docs/tasker-android-setup.md](docs/tasker-android-setup.md) for setup
instructions.

To regenerate the Tasker XML:

```bash
# Pure-Tasker approach (does not work on Android 16)
uv run python -m mvwifi_auto.tasker_gen --output android/MVwifiAuto.prj.xml

# Termux approach (recommended)
uv run python -m mvwifi_auto.tasker_gen --termux -o android/MVwifiAuto-Termux.prj.xml
```

## Costco WiFi Support (Scaffolded)

Costco WiFi has a similar captive portal. The handler is scaffolded in
`src/mvwifi_auto/costco_portal.py` but the actual protocol (endpoint
path, form fields) must be captured on-site.

To capture the Costco portal structure:

```bash
# On a device connected to Costco WiFi:
mvwifi-analyze-portal --probe-url http://1.1.1.1/ --save-html --interface wlan0
```

Then fill in the `COSTCO_LOGIN_URL` and `COSTCO_POST_DATA` constants in
`src/mvwifi_auto/costco_portal.py` from the analyzer output.

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
- `src/mvwifi_auto/captive_portal.py` - Captive portal handling (cmvwifi)
- `src/mvwifi_auto/costco_portal.py` - Costco WiFi portal handler (scaffolded)
- `src/mvwifi_auto/portal_analyzer.py` - Generic portal analysis tool
- `src/mvwifi_auto/wifi_binding.py` - Interface-bound HTTP adapter (Android/Termux)
- `src/mvwifi_auto/android.py` - Android/Termux entry point
- `src/mvwifi_auto/tasker_gen.py` - Tasker XML generator
- `systemd/mvwifi-auto.service` - User systemd service unit
- `android/MVwifiAuto.prj.xml` - Tasker project (generated)

## License

MIT License - See LICENSE file
