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
    ├─ create_wifi_session("wlan0")  # or auto-detect
    │    └─ InterfaceBoundAdapter: source_address + SO_BINDTODEVICE
    │       (kernel-level interface binding, bypasses policy routing)
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
the captive portal. This section provides complete step-by-step
instructions for wiring up the full automatic flow.

### Prerequisites Checklist

Before starting, make sure you have all of these:

- [ ] **Termux** installed (from F-Droid)
- [ ] **Termux:Tasker** installed (from F-Droid)
- [ ] **Python 3.11+** installed in Termux (`pkg install python`)
- [ ] **requests** installed in Termux (`pip install requests`)
- [ ] **MVwifiAuto** cloned and installed in Termux (`pip install -e .`)
- [ ] **Tasker** installed (latest version)
- [ ] **Tasker Settings** helper app installed (required for WiFi
      connection on Android 10+ — see
      [tasker-android-setup.md](tasker-android-setup.md) for details)
- [ ] **cmvwifi** saved in Android WiFi settings with **auto-connect
      turned OFF** (connect once manually, accept the portal, then
      disable auto-connect)

### Import the Tasker Project (Optional)

The repo includes a pre-built Tasker XML for the Termux approach:

```
android/MVwifiAuto-Termux.prj.xml
```

This contains the `ConnectAndRun`, `RunPortalScript`, `DebugFlash`,
`DebugOn`, and `DebugOff` tasks, plus the `cmvwifi Auto Connect`
profile — all pre-configured for the Termux:Tasker plugin.

To import it:

```bash
# Push to phone
adb push android/MVwifiAuto-Termux.prj.xml /sdcard/Tasker/projects/MVwifiAuto-Termux.prj.xml
```

Then in Tasker: long-press the bottom nav bar → **Import Project**
→ select `MVwifiAuto-Termux`.

> **Note**: After import, you still need to create the wrapper script
> (Step 1) and grant the Termux:Tasker permission (Step 2). The XML
> only contains the Tasker tasks and profile — it can't create files
> in Termux or grant permissions.
>
> To regenerate the XML after editing:
> ```bash
> uv run python -m mvwifi_auto.tasker_gen --termux
> ```

### Step 1: Create the Wrapper Script

Termux:Tasker looks for executable scripts in `~/.termux/tasker/`.
Create a wrapper that runs the Python portal handler:

```bash
# In Termux:
mkdir -p ~/.termux/tasker

# Find the full path to mvwifi-android
which mvwifi-android
# Should show: /data/data/com.termux/files/usr/bin/mvwifi-android

# Create the wrapper script using the full path
# (Termux:Tasker runs in a minimal environment without PATH)
cat > ~/.termux/tasker/mvwifi_portal << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
exec /data/data/com.termux/files/usr/bin/mvwifi-android --once
EOF
chmod +x ~/.termux/tasker/mvwifi_portal
```

Test it works:

```bash
~/.termux/tasker/mvwifi_portal
echo "Exit code: $?"
```

It should output logging lines showing interface detection and
portal handling. Exit code 0 means success.

> **Important**: The wrapper script must use the **full path** to
> `mvwifi-android` because the Termux:Tasker plugin runs in a minimal
> environment without the Termux PATH. Using just `mvwifi-android`
> will fail with "no such file".

### Step 2: Enable Termux:Tasker Integration

Two things must be enabled for Tasker to run Termux scripts:

#### 2a: Grant RUN_COMMAND permission to Tasker

Tasker needs permission to run commands in the Termux environment:

1. Open **Android Settings** → **Apps** → **Tasker**
2. Tap **Permissions**
3. Tap **Additional permissions** (may be under a "More" section)
4. Enable **Run commands in Termux environment**

If you don't see "Additional permissions" or "Run commands in Termux
environment", make sure:
- Tasker is version 5.9.3 or newer
- Termux:Tasker is installed and has been opened at least once
- Both Termux and Termux:Tasker are from F-Droid (not Play Store)

You can also grant it via adb:

```bash
adb shell pm grant com.joaomgcd.tasker com.termux.permission.RUN_COMMAND
```

#### 2b: Allow external apps in Termux

Termux must be configured to allow external apps (like Tasker) to run
commands:

```bash
# In Termux:
mkdir -p ~/.termux
echo "allow-external-apps = true" >> ~/.termux/termux.properties
```

Then **force-close Termux** (Settings → Apps → Termux → Force Stop)
and reopen it for the change to take effect.

> **Warning**: This allows any app with the `RUN_COMMAND` permission
> to execute commands in your Termux environment. Only grant the
> permission to apps you trust (like Tasker).

#### 2c: Verify the setup

Test that Tasker can run a simple Termux command:

1. In Termux, create a test script:
   ```bash
   echo '#!/data/data/com.termux/files/usr/bin/sh' > ~/.termux/tasker/test
   echo 'echo "Termux:Tasker works!" > /dev/null' >> ~/.termux/tasker/test
   chmod +x ~/.termux/tasker/test
   ```

2. In Tasker, create a test task with a **Plugin → Termux:Task**
   action, executable: `test`

3. Run the task — if it succeeds without error, the integration is
   working. If you get a permission error, go back and check 2a and 2b.

### Step 3: Create the Portal Handler Task

This task runs the Python script via the Termux:Tasker plugin:

1. Open **Tasker** → **TASKS** tab
2. Tap **+** to create a new task
3. Name: `RunPortalScript`
4. Tap the checkmark to confirm

Add the action:

1. Tap **+** to add an action
2. Select **Plugin**
3. Select **Termux:Task**
4. Configure:
   - **Executable**: `mvwifi_portal`
   - **Arguments**: (leave blank — the script handles everything)
   - **Background**: Yes (checked — no terminal window needed)
5. Tap **back** to save the action
6. Tap **back** to save the task

> **Note**: For Android 10+, if you want foreground execution (with
> a visible terminal), Termux needs "Draw Over Apps" permission.
> Background execution (the default) does not require this and is
> recommended.

### Step 4: Create the Connection Task

This task connects to cmvwifi and then triggers the portal script.
We need a small wait between connecting and running the script so
that DHCP has time to assign an IP address.

1. **TASKS** tab → **+**
2. Name: `ConnectAndRun`
3. Tap the checkmark

Add the actions in order:

**Action 1: Connect to cmvwifi**

1. Tap **+** to add an action
2. Select **Net**
3. Select **Connect to WiFi**
4. **SSID**: `cmvwifi`
5. Tap **back** to save

**Action 2: Wait for DHCP**

1. Tap **+** to add an action
2. Select **Task**
3. Select **Wait**
4. **Seconds**: `5`
5. Tap **back** to save

> **Why 5 seconds?** After connecting to cmvwifi, Android needs a
> moment to associate with the access point and get a DHCP lease.
> Without this wait, the Python script may run before wlan0 has an
> IP address, causing the interface binding to fail. If you still
> see binding errors, increase to 10 seconds.

**Action 3: Run the portal script**

1. Tap **+** to add an action
2. Select **Task**
3. Select **Perform Task**
4. **Name**: `RunPortalScript`
5. Tap **back** to save

**Action 4: (Optional) Flash the result**

To see whether the script succeeded during testing:

1. Tap **+** to add an action
2. Select **Alert**
3. Select **Flash**
4. **Text**: `Portal handling complete`
5. Tap **back** to save

Your `ConnectAndRun` task should now have 4 actions:

```
ConnectAndRun
  A1: Net → Connect to WiFi [ SSID:cmvwifi ]
  A2: Task → Wait [ 5 seconds ]
  A3: Task → Perform Task [ Name:RunPortalScript ]
  A4: Alert → Flash [ Portal handling complete ]
```

### Step 5: Create the WiFi Near Profile

This profile triggers `ConnectAndRun` automatically when cmvwifi
comes into range.

1. Tap the **PROFILES** tab
2. Tap **+** to create a new profile
3. Select **State** (not Time or Event)
4. Select **Net**
5. Select **WiFi Near**
6. **SSID**: `cmvwifi`
7. **MAC**: Leave blank
8. **Toggle**: Make sure it's set to detect when NEAR (not when NOT near)
9. Tap the **back arrow** to save

After saving, you'll see "Enter Task Name":

1. Select **Existing Task**
2. Select `ConnectAndRun`
3. Tap **OK**

Your profile should show:

```
Profile: cmvwifi Auto Connect
  State: WiFi Near [ SSID:cmvwifi ]
Enter Task: ConnectAndRun
```

### Step 6: Handle the "Already Connected" Case

If you're already connected to cmvwifi (e.g. you walked back into
range after a brief disconnection), the `Connect to WiFi` action may
return an error because you're already on that network. Add a check
at the beginning of `ConnectAndRun`:

**Action 1 (new): Check current SSID**

1. In `ConnectAndRun`, tap **+** at the top of the action list
2. Select **Variables**
3. Select **Variable Set**
4. **Name**: `%CurrentSSID`
5. **Value**: `%WIFII`
6. Tap **back** to save

**Action 2 (new): If already on cmvwifi, skip connection**

1. Tap **+** and add an **If** action
2. **Condition**: `%CurrentSSID` `~` `cmvwifi`
3. Tap **back** to save

**Action 3 (new): Goto the script**

1. Tap **+** (inside the If block)
2. Select **Task**
3. Select **Goto**
4. **Type**: `Action Number`
5. **Number**: `5` (the Perform Task action, after adjusting for the
   new actions above)
6. **Label**: (leave blank)
7. Tap **back** to save

**Action 4 (new): End If**

1. Tap **+**
2. Select **Task**
3. Select **End If**
4. Tap **back** to save

Your updated `ConnectAndRun` task:

```
ConnectAndRun
  A1: Variables → Variable Set [ %CurrentSSID = %WIFII ]
  A2: If [ %CurrentSSID ~ cmvwifi ]
  A3: Task → Goto [ Action Number 6 ]
  A4: End If
  A5: Net → Connect to WiFi [ SSID:cmvwifi ]
  A6: Task → Wait [ 5 seconds ]
  A7: Task → Perform Task [ Name:RunPortalScript ]
  A8: Alert → Flash [ Portal handling complete ]
```

> **Note**: The Goto in A3 jumps to A6 (Perform Task), skipping the
> Connect to WiFi and Wait actions when already connected. Adjust the
> action number if you add or remove actions.

### Step 7: Test the Full Flow

**Manual test (near cmvwifi):**

1. Turn WiFi off and on (to reset state)
2. In Tasker, tap the **ConnectAndRun** task to run it manually
3. Watch for:
   - WiFi connects to cmvwifi
   - 5-second wait
   - Python script runs (check with `--verbose` if needed)
   - Flash: "Portal handling complete"
4. Verify internet works (open a browser or app)

**Automatic test:**

1. Walk away from cmvwifi range, then walk back
2. Wait up to 60 seconds for WiFi Near to detect cmvwifi
3. The profile should trigger `ConnectAndRun` automatically
4. Check the Tasker run log (three dots menu → **View Run Log**) to
   confirm it executed

**Debugging with logs:**

If the portal handling fails, add `--verbose --log-file` to the
wrapper script for detailed logging:

```bash
# In Termux, update the wrapper script:
cat > ~/.termux/tasker/mvwifi_portal << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
exec mvwifi-android --once --verbose --log-file ~/storage/shared/mvwifi.log
EOF
```

Then after a failed run, check the log:

```bash
cat ~/storage/shared/mvwifi.log
```

Or transfer it via Google Drive / `adb pull` for easier reading.

### Step 8: Verify the Profile is Active

1. Open Tasker → **PROFILES** tab
2. The `cmvwifi Auto Connect` profile should have a **green dot**
   next to it (active)
3. If it's greyed out, tap the profile to toggle it on

### Profile and Task Summary

After completing all steps, you should have:

**Profile:**
```
cmvwifi Auto Connect
  State: WiFi Near [ SSID:cmvwifi ]
  Enter Task: ConnectAndRun
```

**Tasks:**
```
ConnectAndRun
  A1: Variable Set [ %CurrentSSID = %WIFII ]
  A2: If [ %CurrentSSID ~ cmvwifi ]
  A3: Goto [ Action Number 6 ]
  A4: End If
  A5: Connect to WiFi [ SSID:cmvwifi ]
  A6: Wait [ 5 seconds ]
  A7: Perform Task [ RunPortalScript ]
  A8: Flash [ Portal handling complete ]

RunPortalScript
  A1: Plugin → Termux:Task [ Executable:mvwifi_portal, Background:Yes ]
```

### Troubleshooting Tasker Integration

**"Termux:Task" not appearing in Tasker plugins:**
- Open Termux:Tasker app once (just launch it, then close)
- Open Termux once (just launch it, then close)
- Restart Tasker (force close and reopen)
- Check Tasker → Preferences → Plugin → Termux:Tasker is enabled

**Script runs but portal handling fails:**
- Run the wrapper script manually in Termux to see the error:
  ```bash
  ~/.termux/tasker/mvwifi_portal
  ```
- Add `--verbose --log-file ~/storage/shared/mvwifi.log` to the
  wrapper script for detailed logging
- Make sure WiFi is connected to cmvwifi before the script runs
  (the 5-second wait should be enough, but try increasing it)

**"Connect to WiFi" returns Error 255:**
- You're already connected to cmvwifi — the If/Goto check in
  `ConnectAndRun` should handle this, but if it still happens, just
  run `RunPortalScript` directly

**WiFi Near doesn't trigger:**
- WiFi Near polls periodically (30-60 seconds), not instantly
- Make sure Location is enabled on the phone (WiFi scanning requires
  it on Android 10+)
- Make sure Tasker has Location permission
- Check that the profile is active (green dot in PROFILES tab)

**Script not found:**
- Verify the wrapper script exists: `ls -la ~/.termux/tasker/mvwifi_portal`
- Verify it's executable: `chmod +x ~/.termux/tasker/mvwifi_portal`
- Verify `mvwifi-android` is in PATH: `which mvwifi-android`
- If not found, reinstall: `cd ~/MVwifiAuto && pip install -e .`

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

Once the WiFi Near profile is linked to `ConnectAndRun` (see the
Tasker Integration section above), it will trigger automatically when
cmvwifi comes into range.

### Fallback: Run Shell (without Termux:Tasker)

If you prefer not to use the Termux:Tasker plugin, you can use
Tasker's built-in Run Shell action instead. Replace the
`RunPortalScript` task's Plugin action with:

1. Add action: **Code** → **Run Shell**
2. **Command**: `/data/data/com.termux/files/usr/bin/mvwifi-android --once`
3. **Use Root**: No
4. **Timeout**: 30 seconds
5. **Store Output In**: `%portal_output` (optional, for debugging)

This works but runs in Tasker's minimal shell environment, which may
have PATH issues. The Termux:Tasker plugin is recommended.

## How It Works

1. **Tasker** detects cmvwifi via WiFi Near and triggers `ConnectAndRun`
2. **ConnectAndRun** checks if already connected; if not, connects to
   cmvwifi via Tasker Settings, then waits 5 seconds for DHCP
3. **ConnectAndRun** calls `RunPortalScript` via the Termux:Tasker plugin
4. **Python** creates a `requests.Session` bound to wlan0:
   - `InterfaceBoundAdapter` sets `source_address` to wlan0's local IP
   - `SO_BINDTODEVICE` (socket option 25) forces the kernel to route
     packets through wlan0, bypassing Android's policy routing
   - Source IP binding alone is insufficient — Android ignores it and
     routes over cellular. `SO_BINDTODEVICE` is required.
5. **Python** detects the captive portal by GETting
   `http://detectportal.firefox.com/canonical.html`
   - The portal intercepts and returns a 302 redirect
   - The portal host is extracted from the redirect `Location` header
   - The host is dynamic (e.g. `10.64.2.24:9997`) and differs from the
     default gateway
6. **Python** POSTs to `http://<host>/forms/guest_toued` to accept terms
7. **Python** verifies internet connectivity via
   `http://detectportal.firefox.com/success.txt`

## Troubleshooting

### "Could not determine IPv4 address for interface 'wlan0'"

The interface name may differ on your device. The script auto-detects
the WiFi interface (tries wlan0, wlan1, wlan2, wlan), but you can
specify it manually:

```bash
mvwifi-android --once --interface wlan1
```

To find the correct interface name, run the diagnostic script:

```bash
python scripts/detect_interface.py
```

Note: `ip addr` does not work from Termux (Android blocks netlink
sockets). The ioctl-based detection in the script works fine.

### HTTP requests timing out (cellular is ON)

If requests hang for ~40 seconds and never complete, the interface
binding may not be taking effect. The script uses `SO_BINDTODEVICE`
for kernel-level binding, which should work from Termux without root.
To verify:

```bash
python scripts/test_bindtodevice.py
```

This tests whether `SO_BINDTODEVICE` works on your device. If it
reports "PERMISSION DENIED", your device may need root.

### Logging to a file for debugging

```bash
# Write to Termux home (no permissions needed)
mvwifi-android --once --verbose --log-file ~/mvwifi.log

# Write to shared storage (requires termux-setup-storage)
mvwifi-android --once --verbose --log-file ~/storage/shared/mvwifi.log
```

Then transfer the log via Google Drive, `adb pull`, or `cat` and
copy from the Termux screen.

## Comparison: Termux vs Pure Tasker

| Aspect | Termux + Python | Pure Tasker |
|--------|----------------|-------------|
| Interface binding | Yes (SO_BINDTODEVICE + source IP) | No |
| Reliability | High (same code as laptop) | Race condition dependent |
| Root required | No (SO_BINDTODEVICE works as shell user) | No |
| Tasker Settings needed | Yes (for WiFi connection) | Yes |
| Tasker integration | Termux:Tasker plugin or Run Shell | Native HTTP Request |
| Code reuse | Full (shares captive_portal.py) | None (reimplemented in XML) |
| Testability | 163 unit tests | XML generator tests only |
| Maintenance | Edit Python | Edit Python generator → regenerate XML |

## Files

- `src/mvwifi_auto/android.py` - Termux entry point
- `src/mvwifi_auto/wifi_binding.py` - Interface-bound HTTP adapter
- `src/mvwifi_auto/captive_portal.py` - Shared portal handling
- `src/mvwifi_auto/tasker_gen.py` - Tasker XML generator (for WiFi Near profile)
