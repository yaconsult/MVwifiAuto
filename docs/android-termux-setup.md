# Termux Android Setup Guide for MVwifiAuto

The recommended approach for Android: run the same Python
portal-handling code as the laptop, with HTTP traffic bound to wlan0
to bypass Android's cellular-preferred policy routing.

## Why Termux Over Pure Tasker?

After 17 sessions of fighting Android 16's platform limitations (see
[android-devlog.md](android-devlog.md)), the root causes are clear:

1. **Tasker HTTP Request has no interface binding** — Android 16 policy
   routing sends internet-bound traffic over cellular whenever mobile
   data is on.
2. **Tasker root shell is blocked on Android 16** — the `curl
   --interface wlan0` workaround can't be invoked from Tasker.
3. **Pure Tasker HTTP relies on a race condition** — during initial
   WiFi association, cmvwifi briefly becomes the only default route.
   Not reliable.

The Termux approach reuses the tested Python code and binds HTTP to
wlan0 directly, making it as reliable as the laptop version.

## Architecture

```
Tasker (WiFi Near profile)
    │
    ▼
Run Shell (non-root): mvwifi-android --once
    │
    ▼
Termux Python environment
    │
    ▼
mvwifi_auto.android.run_once()
    │
    ├─ create_wifi_session("wlan0")
    │    └─ InterfaceBoundAdapter binds sockets to wlan0's IP
    │
    └─ handle_cmvwifi_connection(session=...)
         ├─ detect_captive_portal(session=...)
         ├─ extract_portal_host(redirect_url)
         ├─ accept_cmvwifi_terms(portal_host, session=...)
         └─ verify_internet_connectivity(session=...)
```

## Prerequisites

1. **Rooted Google Pixel** with Magisk (for Tasker WiFi connection)
2. **Termux** installed (from F-Droid or GitHub releases, not Play Store)
3. **Termux:Tasker** installed (from F-Droid — optional but recommended for Tasker integration)
4. **Python 3.11+** in Termux
5. **Tasker** with **Tasker Settings** helper app (for WiFi connection)
6. `cmvwifi` network saved in Android WiFi settings — **do not enable auto-connect**

### Install Termux

The Play Store version of Termux is outdated. Install from F-Droid or
GitHub:

```bash
# From F-Droid: https://f-droid.org/packages/com.termux/
# Or download APK: https://github.com/termux/termux-app/releases
```

### Install Python in Termux

Open Termux and run the following commands. Termux uses its own package
manager (`pkg`, which wraps `apt`) — do **not** use the Play Store
version of Termux, as it is outdated and its package repos are
discontinued.

```bash
# Update the package list
pkg update && pkg upgrade -y

# Install Python 3 and pip
pkg install -y python

# Verify installation
python --version   # should show Python 3.11 or newer
pip --version

# Install the requests library (required by mvwifi_auto)
pip install requests

# Install git if you want to clone the repo directly on the phone
pkg install -y git
```

#### Notes

- **Python version**: Termux ships Python 3.11+ on current builds. If
  `python --version` shows an older version, run `pkg upgrade python`.
- **No virtualenv needed**: Termux's environment is already isolated
  from the Android system Python (if any). Installing packages globally
  with `pip` is fine in Termux.
- **Storage access**: If you need to access `/sdcard` from Termux
  (e.g., to copy files from your computer via `adb push`), run:
  ```bash
  termux-setup-storage
  ```
  This creates symlinks to shared storage under `~/storage/`.
- **requests dependencies**: `pip install requests` also installs
  `urllib3`, `certifi`, `charset-normalizer`, and `idna` automatically.

### Install Tasker Settings

See the [Tasker setup guide](tasker-android-setup.md) for Tasker
Settings installation instructions.

## Installation

### Option A: Clone the Repo (if git is available)

```bash
# In Termux:
pkg install git
git clone https://github.com/lpinard/MVwifiAuto.git ~/MVwifiAuto
cd ~/MVwifiAuto
pip install -e .
```

### Option B: Copy Files Manually

If you can't clone from the phone, copy the source files from your
computer:

```bash
# From your computer:
adb push src/mvwifi_auto/ /sdcard/mvwifi_auto/
adb push pyproject.toml /sdcard/mvwifi_auto/

# In Termux:
mkdir -p ~/MVwifiAuto
cp -r /sdcard/mvwifi_auto/* ~/MVwifiAuto/
cd ~/MVwifiAuto
pip install -e .
```

### Verify Installation

```bash
mvwifi-android --once --verbose
```

You should see logging output showing the WiFi-bound session being
created and portal detection running.

## Tasker Integration

Tasker handles WiFi detection and connection; Termux/Python handles
the captive portal.

There are two ways to trigger the Python script from Tasker:

### Option A: Termux:Tasker Plugin (Recommended)

[Termux:Tasker](https://github.com/termux/termux-tasker) is an official
Termux add-on (available on
[F-Droid](https://f-droid.org/en/packages/com.termux.tasker/)) that lets
Tasker execute Termux scripts as a proper plugin action. This is cleaner
than Run Shell because it runs in Termux's full environment — no PATH
issues, no full-path hacks.

#### Install Termux:Tasker

1. Install from F-Droid: `https://f-droid.org/en/packages/com.termux.tasker/`
2. In Tasker: **Preferences** → **Plugin** → grant `com.termux.permission.RUN_COMMAND`

#### Create the wrapper script

In Termux, create a script in the `~/.termux/tasker/` directory (this is
where Termux:Tasker looks for executable scripts):

```bash
mkdir -p ~/.termux/tasker
cat > ~/.termux/tasker/mvwifi_portal << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
exec mvwifi-android --once --verbose
EOF
chmod +x ~/.termux/tasker/mvwifi_portal
```

#### Create the Tasker task

1. Open **Tasker** → **TASKS** tab → **+**
2. Name: `RunPortalScript`
3. Add action: **Plugin** → **Termux:Task**
4. Configure:
   - **Executable**: `mvwifi_portal` (the script in `~/.termux/tasker/`)
   - **Background**: Yes (default — no terminal window needed)
5. Save

> **Note**: For Android >= 10, if you want foreground execution, Termux
> needs "Draw Over Apps" permission. Background execution (the default)
> does not require this.

### Option B: Run Shell (Fallback)

If you don't want to install Termux:Tasker, use Tasker's built-in Run
Shell action. This works but requires full paths since Tasker's shell
has a minimal PATH.

1. Open **Tasker** → **TASKS** tab → **+**
2. Name: `RunPortalScript`
3. Add action: **Code** → **Run Shell**
4. Configure:
   - **Command**: `/data/data/com.termux/files/usr/bin/mvwifi-android --once`
   - **Use Root**: No
   - **Timeout**: 30 seconds
5. Save

### Update the WiFi Near Profile

Use the same WiFi Near profile as the Tasker-only approach, but link
it to `RunPortalScript` instead of `ConnectToCmvwifi`:

1. **PROFILES** tab → your `cmvwifi Auto Connect` profile
2. Tap the linked task → change to `RunPortalScript`

Or create a new combined task:

1. Create task `ConnectAndRun`
2. Action 1: **Net** → **Connect to WiFi** → SSID: `cmvwifi`
3. Action 2: **Wait** → 3 seconds
4. Action 3: **Perform Task** → `RunPortalScript`
5. Link the WiFi Near profile to `ConnectAndRun`

## Usage

### Manual (from Termux)

```bash
# Run once with verbose output
mvwifi-android --once --verbose

# Run with custom interface
mvwifi-android --once --interface wlan1

# Run with more retry attempts
mvwifi-android --once --max-attempts 5
```

### Automatic (via Tasker)

Once the WiFi Near profile is linked to the script-running task, it
will trigger automatically when cmvwifi is in range.

## How It Works

1. **Tasker** detects cmvwifi via WiFi Near and connects using Tasker
   Settings (same as the pure-Tasker approach)
2. **Tasker** runs `mvwifi-android --once` via Run Shell (non-root)
3. **Python** creates a `requests.Session` bound to wlan0:
   - `InterfaceBoundAdapter` sets `source_address` to wlan0's local IP
   - All HTTP traffic goes through wlan0, bypassing cellular policy routing
4. **Python** detects the captive portal by GETting `http://1.1.1.1/`
   - The portal intercepts and redirects to `http://<host>:<port>/...`
   - The host is extracted from the redirect URL
5. **Python** POSTs to `http://<host>/forms/guest_toued` to accept terms
6. **Python** verifies internet connectivity via
   `http://detectportal.firefox.com/success.txt`

## Troubleshooting

### "Could not determine IPv4 address for interface 'wlan0'"

The interface name may differ on your device. Check with:

```bash
ip addr | grep -E "^[0-9]+:"
```

Then specify the correct interface:

```bash
mvwifi-android --once --interface wlan1
```

### Python script not found from Tasker

Termux's PATH may not be available in Tasker's shell. Use the full
path:

```
/data/data/com.termux/files/usr/bin/mvwifi-android --once
```

### Portal detection fails

Turn off mobile data temporarily and run with verbose output:

```bash
mvwifi-android --once --verbose
```

Check that the WiFi-bound session is using the correct source IP. The
verbose output will show the interface and source IP.

### `requests` not installed

```bash
pip install requests
```

## Comparison: Termux vs Pure Tasker

| Aspect | Termux + Python | Pure Tasker |
|--------|----------------|-------------|
| Interface binding | Yes (InterfaceBoundAdapter) | No |
| Reliability | High (same code as laptop) | Race condition dependent |
| Root required | No (non-root shell) | No |
| Tasker Settings needed | Yes (for WiFi connection) | Yes |
| Tasker integration | Termux:Tasker plugin or Run Shell | Native HTTP Request |
| Code reuse | Full (shares captive_portal.py) | None (reimplemented in XML) |
| Testability | 157 unit tests | XML generator tests only |
| Maintenance | Edit Python | Edit Python generator → regenerate XML |

## Files

- `src/mvwifi_auto/android.py` - Termux entry point
- `src/mvwifi_auto/wifi_binding.py` - Interface-bound HTTP adapter
- `src/mvwifi_auto/captive_portal.py` - Shared portal handling
- `src/mvwifi_auto/tasker_gen.py` - Tasker XML generator (for WiFi Near profile)
