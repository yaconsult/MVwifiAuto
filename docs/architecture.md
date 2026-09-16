# MV WiFi Auto - Architecture

## Overview

MV WiFi Auto is a user-space daemon that automatically connects to Mountain View public WiFi (`cmvwifi`) and handles the captive portal acceptance. It integrates with NetworkManager via D-Bus and runs as a user systemd service.

## Components

```
┌─────────────────────────────────────────────────────────┐
│                    User Session                         │
│  ┌─────────────────┐    ┌──────────────────────────────┐ │
│  │ systemd --user  │───▶│ mvwifi-auto.service        │ │
│  └─────────────────┘    │ (runs every 60s)           │ │
│                         └──────────────┬───────────────┘ │
└────────────────────────────────────────┼─────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────┐
│              mvwifi-auto Controller                     │
│  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │ WiFiController   │  │ decide_action()            │  │
│  │                  │  │ - Check current state      │  │
│  │ ┌──────────────┐ │  │ - Scan for networks        │  │
│  │ │ run_once()   │─┼─▶│ - Make decision            │  │
│  │ │ run_daemon() │ │  │ - Execute action           │  │
│  │ └──────────────┘ │  └──────────────────────────┘  │
│  └────────┬─────────┘                                    │
└───────────┼───────────────────────────────────────────────┘
            │
    ┌───────┴───────┐
    │               │
    ▼               ▼
┌──────────┐  ┌──────────────────┐
│ Network  │  │ Captive Portal   │
│ Manager  │  │                  │
│ (D-Bus)  │  │ ┌──────────────┐ │
│          │  │ │ detect()     │ │
│ ┌──────┐ │  │ │ accept()     │ │
│ │ scan │ │  │ │ verify()     │ │
│ │ conn │ │  │ └──────────────┘ │
│ │ info │ │  └──────────────────┘
│ └──────┘ │
└──────────┘
    │
    ▼
┌──────────────────────────────────┐
│      NetworkManager (D-Bus)      │
│  - Device enumeration            │
│  - WiFi scanning                 │
│  - Connection management         │
└──────────────────────────────────┘
```

## Module Breakdown

### `controller.py` - Main Logic

**WiFiController Class**
- `__init__(preferred_networks, public_network, logger)` - Initialize with network lists
- `decide_action(current_ssid, available_networks)` - Core decision logic
- `connect_to_public_wifi()` - Handle cmvwifi connection + portal
- `run_once()` - Single check cycle
- `run_daemon(interval)` - Continuous operation

**Decision Matrix**

| Current State | Preferred Available | Public Available | Action |
|--------------|--------------------|------------------|--------|
| On preferred | - | - | None |
| On public | - | - | None |
| On other | - | - | None |
| Disconnected | Yes | - | Wait (for NM autoconnect) |
| Disconnected | No | Yes | Connect to public |
| Disconnected | No | No | None |

### `network_manager.py` - D-Bus Interface

**NetworkManager Class**
- `get_active_connection_ssid()` - Get currently connected SSID
- `scan_wifi_networks(timeout)` - Scan for available networks
- `connect_to_open_network(ssid)` - Connect via nmcli
- `is_connected_to_internet(host, timeout)` - Ping test

**D-Bus Interfaces Used**
- `org.freedesktop.NetworkManager` - Main interface
- `org.freedesktop.NetworkManager.Device` - Device operations
- `org.freedesktop.NetworkManager.Device.Wireless` - WiFi operations
- `org.freedesktop.NetworkManager.AccessPoint` - AP info

### `captive_portal.py` - Portal Handling

**Key Functions**
- `detect_captive_portal()` - Detect if behind captive portal
- `detect_portal_host()` - Probe for portal host by following a redirect
- `extract_portal_host()` - Extract host (IP or IP:port) from a redirect URL
- `accept_cmvwifi_terms(portal_host)` - Accept Mountain View WiFi terms
- `verify_internet_connectivity()` - Confirm internet access
- `get_default_gateway()` - Get gateway IP from routing table (diagnostics)

**Portal Host Detection**

The portal sign-in host is *not* necessarily the default gateway. The
captive portal redirects HTTP requests to a dynamic host (e.g.
`10.64.2.21:9997`) which may differ from the routing gateway
(`10.65.8.1`). The portal host is extracted from the redirect URL, not
from `ip route`.

**Interface Binding**

All HTTP functions accept an optional `session` parameter (a
`requests.Session`). When `None`, the default `requests` module is
used (Linux/NetworkManager). On Android/Termux, a WiFi-bound session
from `wifi_binding.create_wifi_session()` forces traffic through
wlan0, bypassing cellular policy routing.

**Portal Detection Method**
1. Request `http://detectportal.firefox.com/canonical.html`
2. If redirect (302/307) → captive portal detected
3. If HTML content → captive portal page
4. If "success" response → no portal

**Mountain View WiFi Specifics**
- Open network (no password)
- Captive portal at `http://{portal_host}/forms/guest_toued`
- Portal host extracted from redirect URL (dynamic per session)
- POST with `origurl` and `ok=Accept and Continue`
- Based on implementation in WeatherClock-micropython

### `wifi_binding.py` - Interface-Bound HTTP (Android/Termux)

Binds `requests` HTTP traffic to a specific network interface (e.g.
`wlan0`), equivalent to `curl --interface wlan0`. Required on Android
where policy routing sends internet-bound traffic over cellular.

Uses `SO_BINDTODEVICE` (socket option 25) for kernel-level interface
binding, which bypasses Android's policy routing table entirely. Source
IP binding alone is insufficient — Android's policy routing ignores
the source address and still routes over cellular. `SO_BINDTODEVICE`
forces the kernel to send packets through the named interface
regardless of routing rules. Confirmed working from Termux without
root (the `shell` user has `CAP_NET_RAW`).

**Key Components**
- `get_interface_ip(interface)` - Get IPv4 address via ioctl or `ip addr`
- `detect_wifi_interface()` - Auto-detect active WiFi interface (wlan0/wlan1)
- `InterfaceBoundAdapter` - HTTPAdapter subclass that sets `source_address` and `SO_BINDTODEVICE`
- `create_wifi_session(interface)` - Factory returning a configured Session

### `android.py` - Android/Termux Entry Point

Reuses the same portal-handling logic as the Linux version, but routes
HTTP through a WiFi-bound session. Called from Tasker or run directly
from the Termux command line.

**Key Function**
- `run_once(interface, verbose, max_portal_attempts)` - Single portal cycle
- `main()` - CLI entry point (`mvwifi-android`)

### `tasker_gen.py` - Tasker XML Generator

Generates the Tasker `.prj.xml` file from testable Python data
structures, replacing hand-edited XML. Eliminates parameter-mapping
bugs by encoding Tasker's action/argument format once.

**Key Components**
- Data model: `TaskerProject`, `TaskerTask`, `TaskerAction`, `TaskerArg`
- Action builders: `perform_task()`, `flash()`, `http_request()`,
  `termux_task()`, `goto_action()`, etc.
- `build_mvwifi_project()` - Pure-Tasker project (HTTP Request actions)
- `build_termux_project()` - Termux approach project (Termux:Tasker
  plugin + Python portal handler) — recommended
- `generate_project_xml()` - Serializes to XML string
- CLI: `python -m mvwifi_auto.tasker_gen --termux -o android/MVwifiAuto-Termux.prj.xml`

### `portal_analyzer.py` - Generic Captive Portal Analyzer

A recon tool for capturing the structure of any captive portal — form
actions, hidden fields, submit buttons, redirect URLs.  Originally
written as `analyze_costco_portal.py`, now refactored into a reusable,
testable module.

**Key Components**
- `analyze_portal()` - Probes a URL, follows redirect, parses forms
- `parse_forms(html)` - Extracts forms, fields, checkboxes, hidden inputs
- `PortalReport` - Dataclass with `to_text()` for human-readable output
- CLI: `mvwifi-analyze-portal --probe-url http://1.1.1.1/ --save-html --interface wlan0`

### `costco_portal.py` - Costco WiFi Portal Handler (Scaffolded)

Handles the Costco WiFi captive portal.  Protocol constants (endpoint
path, form fields) are TODO — must be captured on-site using
`mvwifi-analyze-portal`.  The HTTP plumbing (interface binding, redirect
host detection, internet verification) is shared with `captive_portal.py`.

**Key Functions**
- `accept_costco_terms(portal_host, session)` - POST to Costco portal
- `handle_costco_connection(session)` - Full portal handling cycle

**Status**: Scaffolded with placeholder constants.  Run the analyzer on
Costco WiFi to fill in the real values.

## Data Flow

### Normal Operation (On dd-wrt)

```
1. run_once() called
2. get_connection_info() → {ssid: "dd-wrt", has_internet: true}
3. Connected to preferred → return True (no action)
4. Sleep 60s
```

### Transition to cmvwifi

```
1. run_once() called
2. get_connection_info() → {ssid: null, has_internet: false}
3. scan_wifi_networks() → [{ssid: "cmvwifi", ...}]
4. decide_action() → "connect_cmvwifi"
5. connect_to_public_wifi()
   - nmcli device wifi connect cmvwifi
   - handle_cmvwifi_connection()
     - detect_captive_portal() → (true, redirect_url)
     - accept_cmvwifi_terms() → POST to portal
     - verify_internet_connectivity() → true
6. return True
```

### Already on cmvwifi (Portal Re-auth)

```
1. run_once() called
2. get_connection_info() → {ssid: "cmvwifi", has_internet: false}
3. handle_cmvwifi_connection() (re-auth needed)
4. return True
```

## Systemd Integration

### Service File

```ini
[Unit]
Description=Mountain View WiFi Auto-Connect
After=network.target NetworkManager.service

[Service]
Type=simple
Restart=always
RestartSec=10
ExecStart=%h/.local/bin/mvwifi-auto --daemon --interval 60

[Install]
WantedBy=default.target
```

### Resume Service

For handling suspend/resume scenarios where captive portal sessions expire:

```ini
[Unit]
Description=MV WiFi Auto Resume Check
After=suspend.target hibernate.target hybrid-sleep.target NetworkManager.service

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 5
ExecStart=%h/.local/bin/mvwifi-auto --once
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=suspend.target hibernate.target hybrid-sleep.target
```

This service runs once after waking from sleep to handle expired portal sessions.

### User vs System Service

**User Service (Chosen)**
- ✓ No root privileges needed
- ✓ Runs only when user logged in
- ✓ Per-user configuration
- ✗ Requires D-Bus polkit permissions (see below)
- ✗ Requires user session

**System Service (Not Used)**
- Would run as root (overkill for this task)
- Would need careful D-Bus policy configuration
- More complex permission model

## Security Considerations

### D-Bus Access
- Service runs as user → accesses user's NetworkManager session
- Uses system D-Bus (system-wide NetworkManager)
- No privilege escalation needed

### Captive Portal
- Only POSTs to known Mountain View WiFi portal URL
- No credential storage (open network)
- Simple terms acceptance (no personal data)

### Network Scanning
- Uses standard NetworkManager scanning
- No raw socket access needed
- No monitor mode / packet injection

## Error Handling

### NetworkManager Errors
- D-Bus disconnect → Service restarts (systemd `Restart=always`)
- Permission denied → Logged, retry next cycle
- Device not found → Logged, retry next cycle

### Connection Errors
- nmcli failure → Logged, retry next cycle
- Portal timeout → Logged, retry with backoff
- No internet after portal → Retry portal acceptance

## Testing Strategy

### Unit Tests
- Mock D-Bus interfaces
- Mock network responses
- Test decision logic
- Test error handling

### Integration Tests
- Requires real NetworkManager
- Can test scanning (harmless)
- Portal testing requires actual cmvwifi network

### Manual Testing
- Disable WiFi → Verify no action
- Enable cmvwifi → Verify auto-connect
- Disable WiFi, connect to dd-wrt → Verify no interference
- Suspend/resume → Verify service continuity

## Future Improvements

### Possible Enhancements
1. **Configuration file** - Custom networks, intervals
2. **Multiple public networks** - Support for other city WiFi
3. **Signal strength threshold** - Only connect if signal > X
4. **Location awareness** - GPS/geofence to enable/disable
5. **Connection history** - Learn preferred networks over time
6. **GUI indicator** - Show status in system tray
7. **Notification** - Alert on successful cmvwifi connection
