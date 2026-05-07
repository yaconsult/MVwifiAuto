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
- `accept_cmvwifi_terms(gateway_ip)` - Accept Mountain View WiFi terms
- `verify_internet_connectivity()` - Confirm internet access
- `get_default_gateway()` - Get gateway IP from routing table

**Portal Detection Method**
1. Request `http://detectportal.firefox.com/canonical.html`
2. If redirect (302/307) → captive portal detected
3. If HTML content → captive portal page
4. If "success" response → no portal

**Mountain View WiFi Specifics**
- Open network (no password)
- Captive portal at `http://{gateway}/forms/guest_toued`
- POST with `origurl` and `ok=Accept and Continue`
- Based on implementation in WeatherClock-micropython

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
