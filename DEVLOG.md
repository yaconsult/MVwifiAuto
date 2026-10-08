# MV WiFi Auto - Development Log

## 2026-05-07 - Initial Implementation

### Completed
- [x] Project structure with `uv`, `ruff`, `mypy`
- [x] Git repo initialized with main branch
- [x] NetworkManager D-Bus integration
- [x] Captive portal handler for `cmvwifi` (based on micropython reference)
- [x] Decision logic: prefers `dd-wrt`, falls back to `cmvwifi`
- [x] User systemd service unit
- [x] Install script
- [x] Initial README

### Technical Decisions
1. **User systemd service** (not system) - no root needed, runs only when logged in
2. **System site packages** - uses Fedora's `python3-dbus` instead of building from source
3. **Scan interval: 60s** - balance between responsiveness and battery/power usage
4. **Captive portal detection** - uses Firefox's detectportal.firefox.com
5. **nmcli for open networks** - simpler than D-Bus for connecting

### Challenges
- D-Bus requires system site packages on Fedora (python3-dbus is C extension)
- `uv` defaults to isolated venv which can't import system dbus
- Solution: `uv venv --system-site-packages` and `tool.uv.pip.system-site-packages = true`

### Open Questions
- How will this behave on resume from suspend? (systemd should restart service)
- Need to test actual cmvwifi captive portal flow

### 2026-05-07 - Documentation and Tests

#### Completed
- [x] Created comprehensive test suite with pytest
- [x] Added architecture documentation (docs/architecture.md)
- [x] Added troubleshooting guide (docs/troubleshooting.md)
- [x] Updated pyproject.toml with test configuration
- [x] Created test fixtures for mocking D-Bus and network

#### Testing
- 47 test cases covering:
  - Controller decision logic (10 tests)
  - Captive portal detection (9 tests)
  - Portal terms acceptance (6 tests)
  - NetworkManager interface (14 tests)
  - Internet connectivity verification (4 tests)
  - Gateway detection (3 tests)

#### Documentation
- Architecture diagram with component breakdown
- Decision matrix for connection logic
- Data flow diagrams for common scenarios
- Troubleshooting guide with common issues
- Debug and manual testing procedures

### Next Steps
- [x] Test on actual cmvwifi network - Done, working!
- [x] Install and configure on user system - Done
- [ ] Consider adding config file support
- [ ] Add logging to file option
- [ ] Add integration tests
- [ ] Create CI/CD workflow

### 2026-05-07 - Installation and Real-World Testing

#### Completed
- [x] Installed on user's Fedora laptop
- [x] Fixed D-Bus permission error with polkit rule
- [x] Created resume service for suspend/hibernate handling
- [x] Replaced magic number (2) with NM_DEVICE_TYPE_WIFI constant
- [x] Cleaned up debug print statements
- [x] Tested disconnect/reconnect behavior

#### Technical Decisions
1. **Polkit rule required** - Systemd user service needs explicit D-Bus permissions for NetworkManager
2. **Resume service as oneshot** - Triggers once after wake, runs connectivity check
3. **Constants for NM device types** - Magic number 2 → NM_DEVICE_TYPE_WIFI = 2

#### Challenges
- **D-Bus AccessDenied** - User systemd service couldn't query NetworkManager without polkit rule
  - Solution: Created `/etc/polkit-1/rules.d/50-mvwifi-auto.rules`
- **Recursive uv run** - Wrapper script called itself infinitely
  - Solution: Changed from `uv run mvwifi-auto` to `uv run python -m mvwifi_auto.cli`

#### Testing
- Connected to cmvwifi: ✓ Detected correctly
- Manual disconnect: ✓ NetworkManager autoreconnects before service check (expected)
- Service active: ✓ Running every 60s, doing nothing when already connected (correct)
- D-Bus permissions: ✓ Fixed with polkit rule

#### Next Steps
- Monitor for actual captive portal scenarios
- Document polkit requirement in install.sh

## 2026-09-14 - Portal Host Fix, Android Termux Port, Tasker XML Generator, Costco Scaffold

### Completed
- [x] Fixed `captive_portal.py` to extract portal host from redirect URL instead of using default gateway IP
- [x] Added `extract_portal_host()` and `detect_portal_host()` functions
- [x] Added `session` parameter to all HTTP functions for interface binding
- [x] Created `wifi_binding.py` — `InterfaceBoundAdapter` that binds sockets to wlan0 (like `curl --interface`)
- [x] Created `android.py` — Termux entry point that reuses Python portal logic with WiFi-bound session
- [x] Created `tasker_gen.py` — testable Python generator for Tasker `.prj.xml` files
- [x] Regenerated `android/MVwifiAuto.prj.xml` from the generator
- [x] Added `mvwifi-android` console script entry point
- [x] Refactored `analyze_costco_portal.py` into `mvwifi_auto/portal_analyzer.py` (generic, testable)
- [x] Scaffolded `mvwifi_auto/costco_portal.py` with TODOs for on-site protocol capture
- [x] Added `mvwifi-analyze-portal` console script entry point
- [x] Updated all tests (157 pass, 4 skipped)
- [x] Updated documentation

### Technical Decisions
1. **Redirect host over gateway IP** — The portal sign-in host (`10.64.2.21:9997`) differs from the routing gateway (`10.65.8.1`). The Android devlog identified this in Session 14. Now both implementations extract the host from the redirect `Location` header, sharing a single source of truth.
2. **Session parameter for interface binding** — All HTTP functions in `captive_portal.py` accept an optional `requests.Session`. On Linux, `None` uses the default module. On Android, `create_wifi_session("wlan0")` returns a session that binds all sockets to wlan0's local IP, bypassing cellular policy routing.
3. **Termux + Python over pure Tasker** — After 17 sessions of fighting Android 16's platform limitations (blocked root shell, no interface binding in Tasker HTTP, policy routing), the Android port now runs the same Python code as the laptop via Termux. Tasker's role is reduced to WiFi Near detection + triggering the Python script.
4. **Testable XML generator** — Replaced hand-edited XML with `tasker_gen.py` that builds Tasker projects from Python dataclasses. Parameter-mapping bugs (Sessions 14, 17) are now structurally impossible — the generator encodes the correct arg ordering once.

### Challenges
- **Mocked requests exceptions** — When `requests` is patched by pytest, `requests.RequestException` becomes a MagicMock and can't be caught. Fixed by importing the real exception classes at module level (`_RequestsRequestException`, etc.).
- **`detect_portal_host` false positive** — When no redirect occurs, `response.url == probe_url`. Added an explicit check to return `None` in that case.
- **ElementTree pretty-printing** — `tostring()` produces single-line output. Used `xml.etree.ElementTree.indent()` (Python 3.9+) with tab indentation to match Tasker's export format.

### Testing
- 115 tests pass, 4 skipped (D-Bus tests requiring real NetworkManager)
- New test files: `test_wifi_binding.py` (10 tests), `test_android.py` (10 tests), `test_tasker_gen.py` (33 tests)
- Updated `test_captive_portal.py`: 30 tests (was 18) covering new `extract_portal_host`, `detect_portal_host`, and `session` parameter
- Generated XML validated with `xmllint --noout`

### Next Steps
- [ ] Test Termux approach on actual Android device near cmvwifi
- [ ] Run `mvwifi-analyze-portal` on Costco WiFi to capture portal protocol
- [ ] Fill in `costco_portal.py` constants from analyzer output
- [ ] Export final working XML from phone for reference
- [ ] Consider CI/CD workflow
- [ ] Add config file support

---

## 2026-09-15 - SO_BINDTODEVICE Fix, Android Portal Flow Verified, Home SSID Update

### Completed
- [x] Added `SO_BINDTODEVICE` to `InterfaceBoundAdapter` for kernel-level interface binding
- [x] Verified full captive portal flow on Android with cellular ON
- [x] Added `--log-file` option to `mvwifi-android` for on-device debugging
- [x] Added auto-detection of WiFi interface (wlan0/wlan1)
- [x] Added `dd-wrt_5G` to `PREFERRED_NETWORKS` so both home SSIDs are recognized
- [x] Fixed `install.sh` to derive repo path from script location (no hardcoded `PycharmProjects`)
- [x] Redeployed laptop service with new code
- [x] Updated all documentation

### Technical Decisions
1. **SO_BINDTODEVICE over source-IP-only binding** — The original `InterfaceBoundAdapter` only set `source_address` (the interface's local IP). On Android, policy routing ignores source IP binding and still routes packets over cellular. `SO_BINDTODEVICE` (socket option 25) forces the kernel to route packets through the named interface at the kernel level, bypassing policy routing entirely. This is what `curl --interface` does internally. Confirmed working from Termux without root on a Pixel device.
2. **Auto-detection of WiFi interface** — Pixel devices may use `wlan0` or `wlan1`. The ioctl-based detection tries each candidate and returns the first with an IP. Eliminates the need for `--interface` in normal use.
3. **Both home SSIDs as preferred** — `dd-wrt` (2.4 GHz) and `dd-wrt_5G` (5 GHz) are both saved networks that auto-connect at home. Adding both to `PREFERRED_NETWORKS` prevents the service from trying to switch to `cmvwifi` when connected to the 5 GHz network.

### Key Findings (Android)
- **Source IP binding is insufficient on Android** — Android's policy routing table overrides source IP binding. HTTP requests with the correct wlan0 source IP still went over cellular, causing 40-second timeouts.
- **SO_BINDTODEVICE works from Termux without root** — The `shell` user (which Termux runs as) has `CAP_NET_RAW`, allowing `SO_BINDTODEVICE` on sockets. No root or Magisk needed for the HTTP binding.
- **`ip addr` is blocked from Termux** — Android blocks netlink sockets for non-system apps. The ioctl path (`SIOCGIFADDR`) works fine as a fallback.
- **Portal host was `10.64.2.24:9997`** — Confirmed that the portal host differs from the default gateway (`10.65.8.1`), validating the redirect-based host extraction approach.
- **Full flow verified with cellular ON** — Portal detection (302), host extraction, POST acceptance (302), and internet verification (200) all succeeded with mobile data enabled.

### Testing
- 163 tests pass, 4 skipped (D-Bus tests requiring real NetworkManager)
- New tests for `SO_BINDTODEVICE` socket options in `test_wifi_binding.py` (16 total, was 10)
- ruff: all checks passed
- mypy: no issues found in 10 source files
- On-device verification: full portal flow completed successfully with cellular ON

### Files Updated
- **Modified**: `src/mvwifi_auto/wifi_binding.py` — added `SO_BINDTODEVICE` via `socket_options`
- **Modified**: `src/mvwifi_auto/android.py` — added `--log-file` option, moved logging setup to `main()`
- **Modified**: `src/mvwifi_auto/controller.py` — added `dd-wrt_5G` to `PREFERRED_NETWORKS`
- **Modified**: `tests/test_wifi_binding.py` — added SO_BINDTODEVICE tests
- **Modified**: `tests/test_controller.py` — updated preferred networks test
- **New**: `scripts/test_bindtodevice.py` — on-device diagnostic for SO_BINDTODEVICE
- **New**: `scripts/detect_interface.py` — on-device interface detection diagnostic
- **Modified**: `install.sh` — portable repo path detection
- **Docs**: DEVLOG, android-devlog, architecture, troubleshooting, android-termux-setup, README

### Next Steps
- [x] Wire up Tasker integration (Termux:Tasker plugin or Run Shell)
- [x] Test Tasker WiFi Near profile triggering `mvwifi-android`
- [ ] Run `mvwifi-analyze-portal` on Costco WiFi to capture portal protocol
- [ ] Fill in `costco_portal.py` constants from analyzer output

---

## 2026-09-15: Tasker + Termux:Tasker Integration Verified

### Summary
Successfully wired up Tasker to automatically trigger `mvwifi-android`
via the Termux:Tasker plugin. The full chain works end-to-end:
Tasker → Termux:Tasker plugin → wrapper script → Python portal handler.

### Key Changes
- **Fixed Termux:Tasker plugin action format** — The plugin uses
  action code `1256900802` (not 130) with a specific Bundle structure
  matching the official Termux:Tasker template
- **Fixed Bundle XML generation** — Bundle contents must be child
  elements, not escaped text, or Tasker can't parse them
- **Log-on-failure behavior** — Log file is deleted on success, kept
  only on failure, making it easy to check for problems
- **Deployment scripts** — `scripts/deploy_android.sh` (PC-side via
  adb) and `scripts/termux_setup.sh` (Termux-side)
- **Importable Tasker XML** — `android/MVwifiAuto-Termux.prj.xml`
  with `ConnectAndRun`, `RunPortalScript`, and WiFi Near profile

### Verification
Running `RunPortalScript` from Tasker produced a successful log:
- Auto-detected `wlan0` with `SO_BINDTODEVICE`
- Portal check returned 200 (no portal at home)
- Internet verification returned 200 (success)

### Testing
- 178 tests pass, 4 skipped
- 13 new tests for Termux project in `test_tasker_gen.py`
- 3 new tests for log-on-failure behavior in `test_android.py`
- ruff: all checks passed
- mypy: no issues found

### Files Updated
- **Modified**: `src/mvwifi_auto/tasker_gen.py` — fixed Bundle
  generation, added `termux_task()`, `goto_action()`,
  `build_termux_project()`
- **Modified**: `src/mvwifi_auto/android.py` — log file deleted on
  success
- **Modified**: `tests/test_tasker_gen.py` — 13 new tests
- **Modified**: `tests/test_android.py` — 3 new tests
- **New**: `android/MVwifiAuto-Termux.prj.xml` — importable Tasker
  project for the Termux approach
- **New**: `scripts/deploy_android.sh` — PC-side deployment via adb
- **New**: `scripts/termux_setup.sh` — Termux-side setup
- **Docs**: DEVLOG, android-devlog, android-termux-setup,
  troubleshooting

### Next Steps
- [ ] Test the full automatic flow near cmvwifi (library, Shoreline Park)
- [ ] Run `mvwifi-analyze-portal` on Costco WiFi to capture portal protocol
- [ ] Fill in `costco_portal.py` constants from analyzer output

---

## 2026-09-16 - WiFi Near Parameter Order Fix

### Problem
The `cmvwifi Auto Connect` profile was enabled but never activated
when near cmvwifi. WiFi Near scanning worked (Tasker could see the
network in scan results), but the profile never turned green.

### Root Cause
The generated `MVwifiAuto-Termux.prj.xml` had the WiFi Near state
args in the wrong order:

```
arg0: Str "cmvwifi"   (SSID — correct)
arg1: Int 0           (WRONG — should be Str for MAC)
arg2: Str ""          (WRONG — should be Str for Capabilities)
arg3: Str ""          (WRONG — should be Int for Min Signal)
```

When Tasker imported this, it normalized the args to its internal
format. Our `Int 0` for arg1 became `Str "0"` for the MAC field —
meaning the profile was looking for a network with MAC address "0",
which never matches anything.

### The Fix
Corrected the WiFi Near state arg order in `tasker_gen.py` to match
Tasker's expected format:

```
arg0: Str "cmvwifi"   (SSID)
arg1: Str ""          (MAC — empty = any)
arg2: Str ""          (Capabilities — empty = any)
arg3: Int 0           (Min Activate Signal Level)
arg4: Int 0           (Channel — 0 = any)
arg5: Int 0           (Toggle WiFi — 0 = off)
```

This affects both `build_mvwifi_project()` and
`build_termux_project()` in `tasker_gen.py`.

### Verification
1. Imported corrected `test_wifinear_v2.prj.xml` with WiFi Near
   profile for `dd-wrt` (visible at home)
2. Profile activated immediately — `%PACTIVE` showed
   `WiFiNear-ddwrt-v2` as active
3. Confirmed WiFi Near works correctly on Android 16 with the
   proper arg format

### Key Finding
Tasker normalizes imported args by type, not by index. If an Int
is sent where a Str is expected (or vice versa), Tasker converts
the value type but keeps it in the wrong position. This makes
parameter-order bugs silently fatal — the profile imports but
never matches.

### Why the Bug Existed
The wrong arg order was introduced in the original `tasker_gen.py`
commit (`e9d97ab`). The args were guessed based on the Tasker UI
fields (SSID, Min Signal, Channel, Toggle WiFi) rather than
verified against an actual exported WiFi Near profile. The real
order (SSID, MAC, Capabilities, Min Signal, Channel, Toggle WiFi)
differs — MAC and Capabilities come before the numeric fields.
The bug wasn't caught because Tasker imports the profile without
errors; it just never matches. Real-device testing was the only
way to find it.

### Testing
- 179 tests pass, 4 skipped
- New test `test_wifi_near_state_args` verifies correct arg
  types and order
- ruff: all checks passed
- mypy: no issues found

### Files Updated
- `src/mvwifi_auto/tasker_gen.py` — fixed WiFi Near arg order
- `tests/test_tasker_gen.py` — added `test_wifi_near_state_args`
- `android/MVwifiAuto.prj.xml` — regenerated with correct format
- `android/MVwifiAuto-Termux.prj.xml` — regenerated with correct format

### Next Steps
- [x] Test the full automatic flow near cmvwifi (library, Shoreline Park) — DONE 2026-09-17
- [ ] Run `mvwifi-analyze-portal` on Costco WiFi to capture portal protocol
- [ ] Fill in `costco_portal.py` constants from analyzer output

---

## 2026-09-17 - First Real-World cmvwifi Test: SUCCESS

### Result
The full automatic flow worked at a real cmvwifi location.
WiFi Near detected the network before association, Tasker
connected, Termux:Tasker ran the portal script, terms were
accepted, and the phone got working internet.

### Observed Delay (expected, not a bug)
Several minutes elapsed between the "Portal handling complete"
toast and the phone showing a working WiFi connection. This is
Android's own connectivity validation — the OS re-runs its
captive portal check and only switches the default route from
cellular to WiFi after validation passes. Android batches these
checks; 1-3 minutes is normal when cellular is active.

### Status
All major components confirmed working end-to-end on Android 16:
WiFi Near trigger, Connect to WiFi, Termux:Tasker plugin,
WiFi-bound HTTP session, dynamic portal-host extraction, terms
POST, internet verification, log-on-failure.

### Post-Test Cleanup
- Deleted `analyze_costco_portal.py` (superseded by
  `portal_analyzer.py` + `mvwifi-analyze-portal` CLI) — also
  resolved the last 21 ruff errors in the repo
- Removed debug infrastructure from `tasker_gen.py`:
  `DebugFlash`/`DebugOn`/`DebugOff`/`TestWiFiScan` tasks,
  `debug_flash()` builder, curl-availability check in
  `HandlePortal`, and all `debug_flash()` call sites. Both
  generated projects now contain only production tasks
- Converted `HandlePortal` success/failure `debug_flash` calls
  to regular `flash()` so the pure-Tasker reference project
  still reports its result
- Regenerated `android/MVwifiAuto.prj.xml` (6→2 tasks) and
  `android/MVwifiAuto-Termux.prj.xml` (5→2 tasks)
- Kept: `--verbose` in wrapper scripts (log deleted on success),
  `Flash "Portal handling complete"` (only user-facing signal),
  `%CurrentSSID` set (required by If/Goto), diagnostic scripts
  in `scripts/`

### Linux Service Execution Model (confirmed)
The systemd service runs code directly from the repo — no deploy
step needed. `install.sh` resolves the repo path from its own
location and generates `~/.local/bin/mvwifi-auto` (sets
`PYTHONPATH=<repo>/src`, runs `python3 -m mvwifi_auto.cli` with
system python). `git pull` + `systemctl --user restart
mvwifi-auto` picks up all changes. No separate deploy script is
needed — `install.sh` already serves that role.

### Next Steps
- [ ] Repeat at other cmvwifi locations to confirm consistency
- [ ] Verify failure path retains `mvwifi_tasker.log`
- [ ] Run `mvwifi-analyze-portal` on Costco WiFi — full runbook:
  `docs/costco-portal-capture.md`
- [ ] Fill in `costco_portal.py` constants from analyzer output

---

## 2026-09-17 - Design Notes: Generic Portal Engine

Ideas for evolving from a cmvwifi-specific tool to a generic
captive-portal acceptor usable by others.

### Portal Pattern Taxonomy (observed + expected)

| Pattern | Example | Handling |
|---------|---------|----------|
| Button only | cmvwifi | POST form fields (origurl + ok) |
| Checkbox + button | (expected for some portals) | POST fields + checkbox name/value |
| Login required / OAuth | Costco Member Wifi (likely), xfinitywifi | JS-rendered portal, app/SSO auth — probably not POST-replayable; see below |
| Email/data capture | hotels, airports | Needs user-supplied data — config per field |
| Multi-step / JS | Costco Member Wifi, carriers | Raw HTML is a blank shell — analyzer can't parse; needs dev-tools capture |

**Costco update (2026-09-17, first visit):** SSID confirmed as
`Costco Member Wifi` (open, enterprise multi-SSID APs). The probe
redirects but returns a blank page to curl — the portal is
JS-rendered, and the login flow delegates to the Costco
app/Costco.com account (likely Azure AD B2C). This probably makes
Costco a "login-required" portal, not checkbox+button. If
confirmed: the realistic Android goal shifts from auto-accept to
"auto-connect + notify to sign in", plus check session
persistence (does Costco authorize the device for days?).

### Config-Driven Engine (proposed)

The portal-specific surface is tiny — ~4 constants per portal.
Sketch:

```toml
[[portal]]
ssid = "cmvwifi"
endpoint = "/forms/guest_toued"
[portal.fields]
origurl = "http://www.google.com"
ok = "Accept and Continue"

[[portal]]
ssid = "CostcoWiFi"
endpoint = "TBD-from-capture"
[portal.fields]
accept = "1"      # checkbox — confirmed required
ok = "TBD"
```

This collapses `captive_portal.py` + `costco_portal.py` into one
generic engine + data. **Do this refactor after Costco capture
works** — two real implementations keep the abstraction honest.

### Auto-Submit Heuristic (stretch)

The analyzer already parses forms. An auto-submitter could:
fetch portal page → include hidden fields verbatim → check
required checkboxes → submit → verify. Covers the "accept terms"
family (cmvwifi, Costco, most municipal WiFi). Fails on
multi-step/JS/data-required portals → config override stays as
fallback. Design: **auto-submit first, config as fallback** —
not instead of.

### Which Portal Am I On? (the seam)

Generic version needs to identify the current network:
- Android: Tasker passes `%WIFII` to the task, or read SSID from
  Android; map SSID → handler from config
- Linux: `get_connection_info()` already returns the SSID

### Multi-SSID WiFi Near (Tasker)

Tasker's WiFi Near SSID field supports pattern matching —
`cmvwifi/CostcoWiFi` (slash = OR) matches either network in a
single profile. Alternatives:

- One profile with `ssid1/ssid2` pattern — simplest, and the
  task can branch on which AP was detected
- Separate profile per SSID, all linking to the same task —
  clearer in the UI, more profiles to manage

A single multi-SSID profile is probably sufficient since the
task only needs to know "connect to the SSID we just saw."

### xfinitywifi Extension (deferred)

Open `xfinitywifi` hotspots at customer locations usually
require an Xfinity account login (or a complimentary-pass flow
needing an email). That's the "login required" pattern — a
different feature: stored credentials, config secrets handling,
probably a form-fill POST like the others but with real user
data. Defer until the generic engine exists; would need secure
credential storage (not plaintext config).

Update 2026-10-05: the secure alternative is dead too — the
`Xfinity Mobile` SSID (WPA2-EAP + Passpoint) rejected an
internet-only Xfinity ID (`AUTH_FAILURE_EAP_FAILURE` followed by
`ASSOCIATION_REJECTION`, observed on-device). EAP is gated to
Xfinity Mobile lines; the open `xfinitywifi` portal is the only
route for this account type.

### Prior Art

OpenWrt `travelmate` and GL.iNet travel routers already do
auto-captive-portal login — proven concept, but nothing packaged
nicely for Android/Termux. Real niche if we go generic.

### Decision Path

1. Capture Costco, fill `costco_portal.py` (current plan)
2. Refactor to config-driven engine (2 real portals)
3. Optional: auto-submit heuristic
4. Optional: xfinity/login-required portals (needs credential storage)
5. Publishing for external users — separate decision, don't pay
   that cost until 2+ portals proven

---

## 2026-10-02 - Android: cmvwifi Auto-Join Nudge

### Completed
- [x] Diagnosed the 15-30 min cmvwifi join delay as Android network
      selector backoff (portal "no internet" verdicts + historical
      DHCP/association failures + screen-off PNO scan throttling), not
      Tasker/Termux — handler ran in 9 s once associated
- [x] `src/mvwifi_auto/root_shell.py` — `find_su`/`run_root` extracted
      from `costco_probe.py` (shared root discovery)
- [x] `src/mvwifi_auto/wifi_nudge.py` (`mvwifi-nudge`) — parses
      `cmd wifi status`/`list-scan-results`, issues
      `cmd wifi connect-network` only when target visible and not
      associated; `--dry-run`/`--json`/`--markdown`
- [x] `android/cmvwifi_nudge` wrapper (wake lock, bounded history log)
- [x] `tasker_gen.py`: `TaskerTime` context + `NudgeWifi` task (id=100)
      + `cmvwifi Periodic Nudge` profile (every 15 min); Termux XML
      regenerated
- [x] `deploy_android.sh`/`termux_setup.sh`/`verify_android.sh`
      updated for the new wrapper and modules
- [x] Docs updated (termux-setup, troubleshooting, android-devlog)

### Technical Decisions
1. **Periodic Time profile over WiFi Near/Display On** — WiFi Near
   inherits the same ~30-min background scan throttle; screen-on
   already triggers Android's own retry (connected within 1 s once
   the screen lit up). A 15-min timer directly covers the dead zone.
2. **Never disrupt a working link** — the nudge exits if any WiFi is
   connected; it only acts when disconnected and a target is visible.
3. **`python -m` invocation in the wrapper** — editable install picks
   up new modules on `git pull` without reinstalling entry points.

### Testing
- 251 tests pass; mypy strict + ruff clean
- Parsers verified against real `cmd wifi` output captured on-device
- Field test pending: watch `mvwifi_history.log` for `nudge` →
  `ConnectAndRun fired` latency

---

## 2026-10-05 - Field Failure: Imported Profiles Dormant Until Tasker Opened

### Finding
Three days of silence after the Oct-2 re-import — neither the Time
profile nor WiFi Connected fired, despite being enabled, whitelisted,
and Tasker's process running 12 days. Opening Tasker registered the
contexts: `ConnectAndRun` fired on the next association (8s portal),
`NudgeWifi` on schedule at 11:15. Documented in setup/troubleshooting
and the deploy script now tells users to open Tasker after import.

### Also resolved
- `Xfinity Mobile` EAP rejected the internet-only Xfinity ID
  (`AUTH_FAILURE_EAP_FAILURE`) — secure-SSID shortcut dead; open
  `xfinitywifi` portal automation is the only route for that network
  (still deferred pending the generic engine).

## 2026-10-05 - Android: Action Labels in Generated Tasker XML

### Completed
- `TaskerAction` gained a `label` field, serialized as `<label>` —
  Tasker has no comment syntax; action labels are the closest
  equivalent, shown next to each action in the editor.
- Labeled the opaque actions in all four Termux tasks: Termux plugin
  calls (code 1256900802 renders unintelligibly in the UI), history
  markers, the self-heal shell command, and the DHCP wait. End If /
  Flash etc. left unlabeled (self-describing).
- Regenerated both project XMLs; new `TestActionLabels` class covers
  emission, omission, and that every Termux plugin action is labeled.
- Field verification the same day: nudge forced a cmvwifi join at
  17:30 (`connect-network` rc=0 while disconnected), cmvwifi portal
  handled in 4s at 17:17, Costco Mist TOS-accept at 18:15 (~16s).

### Note
XML change only — takes effect on the phone at the next project
re-import (remember: open Tasker once afterward to activate contexts).

## 2026-10-05 - Android: xfinitywifi Fallback Tier + Promotion

### Discovery
- `xfinitywifi` serves real internet with **no portal** on
  home-gateway hotspots (verified live: HTTPS 200 over wlan0, Comcast
  egress IP). The deferred "login portal" feature is unnecessary.

### Completed
- `wifi_nudge.py`: `--fallback` (demotable connections — promote onto
  a visible preferred SSID) + `--autojoin-disabled` (`-d` on
  connect-network: saved but never self-joined by Android)
- Wrapper generalized: `cmvwifi_nudge` → `wifi_nudge`, forwards "$@";
  SSID sets now live in the Tasker tasks' Arguments field
- Tasker: new `NudgeXfinity` task + `xfinitywifi Periodic Nudge`
  profile; `NudgeWifi` args `--ssid cmvwifi --fallback xfinitywifi`.
  Profile toggle = user-facing on/off for the xfinity tier

### Decisions
- Fallback joined only while fully disconnected; promotion moves the
  phone to a preferred network when one appears
- Promotion path differs by destination: cmvwifi via nudge code
  (open SSID, poisoned score); dd-wrt/Costco via Android's native
  selector (autojoin on, higher score). Nudge can't promote onto
  secured networks — `connect-network` requires the passphrase,
  which is deliberately not stored
- `-d` instead of forget/re-add churn (verified on-device:
  `allowAutojoin=false` on saved netId 10)
- Per-network Tasker profiles as the toggle UI (not a flag file);
  disabling xfinity gates joining only — promotion away still works

## 2026-10-05 - Field Failure: Project Import Merges, Doesn't Replace

### Finding
- Re-importing `MVwifiAuto-Termux` over the existing project silently
  **merged**: old task definitions survived (scheduled `NudgeWifi`
  kept invoking the renamed `cmvwifi_nudge` wrapper) while only the
  new elements (`NudgeXfinity`, `xfinitywifi Periodic Nudge`) were
  added. New profile's Time context never registered — markers absent
  while the ghost task fired every 15 min.
- Diagnostics that proved it: logcat `TermuxTasker.FireReceiver`
  "executable not found" errors for `cmvwifi_nudge`, then a tagged
  compat shim writing `nudge via shim (stale tasker task)` to the
  history log — the scheduled runs were arriving via the shim.
- Fix: **delete the project tab first, then import**, then relaunch
  Tasker once. Verified at the 23:45 tick: both profiles fired, both
  wrappers ran directly (no shim tag), correct
  `action=connected_elsewhere` no-ops on dd-wrt_5G.
- The `cmvwifi_nudge` shim now permanently tags shim invocations —
  any future stale-reference regression is visible in the history log
  instead of failing silently.
- Added a generation stamp: `generate_project_xml` hashes the
  serialized XML and injects `[gen xxxxxx]` into every task marker
  plus a manual `ShowVersion` task (flashes the gen id in the GUI).
  A stale/merged import is now identifiable from the history log or
  one tap — no adb, no logcat needed.

## 2026-10-06 - Android: MVwifi Alternate SSID + Nudge Deferral

### Field observations
- Phone associated to `MVwifi` — an alternate SSID for the same
  municipal network — which was completely unmanaged.
- Connect race at a shared 15-min tick: both nudge tasks issued
  `connect-network` ~34 ms apart while disconnected (Android picked
  cmvwifi; could have been the fallback).

### Changes
- `wifi_nudge.py --defer-to SSID`: a disconnected run exits as
  `deferred` when a preferred SSID is visible — fallback can't race
  preferred joins.
- `MVwifi` added as a preferred nudge target + `MVwifi Auto Connect`
  profile; `ConnectAndRun` accepts either municipal SSID.
- `NudgeXfinity` defers to cmvwifi/MVwifi/dd-wrt/dd-wrt_5G. `Costco
  Member Wifi` excluded — multi-word SSIDs can't survive Termux's
  space-separated Arguments field.
- New action value: `deferred`.

## 2026-10-07 - Android: `--defer-to-preferred` Closes the Costco Gap

### Field failure
At Costco (~15:30), the xfinity nudge issued `connect-network
xfinitywifi` while Costco Member Wifi was in range — the defer list
couldn't carry a multi-word SSID through Termux's space-separated
Arguments field. Phone reached Costco ~15 min late.

### Changes
- `PREFERRED_SSIDS` module constant (cmvwifi, MVwifi, Costco Member
  Wifi, dd-wrt, dd-wrt_5G) + `--defer-to-preferred` flag — the
  multi-word Costco SSID now defers correctly without ever crossing
  the Tasker args boundary.
- `NudgeXfinity` args simplified to `--defer-to-preferred`.
- Guard: a defer entry matching the run's own target never self-defers.

---

## 2026-10-07 - Android: `--preferred` Ranks the Open Networks

### Goal
Rank the preferred tier for real: `NudgeWifi` should target *every*
joinable preferred SSID — not just cmvwifi/MVwifi — so on-xfinity
promotion and disconnected joins work at Costco too.

### Changes
- `PREFERRED_OPEN_SSIDS` constant (cmvwifi, MVwifi, Costco Member
  Wifi) — the nudge-joinable subset of `PREFERRED_SSIDS`. dd-wrt /
  dd-wrt_5G are excluded: `connect-network` can't supply a passphrase
  (never stored) and there's no `disconnect` command in `cmd wifi`,
  so secured-network promotion remains Android-selector territory.
- New `--preferred` flag expands `PREFERRED_OPEN_SSIDS` into the
  target list — the only way the multi-word Costco SSID can be a
  nudge target (Termux Arguments can't carry it).
- `NudgeWifi` args simplified to `--preferred --fallback xfinitywifi`.
- Effect: disconnected at Costco → nudge joins Costco Member Wifi
  directly; on xfinitywifi + Costco visible → `promoted` (previously
  this waited for Android's selector — ~15 min observed).

### Tests
278 pass. New: `--preferred` CLI expansion, `connect-network 'Costco
Member Wifi' open` promotion with quoted multi-word SSID.

### Also fixed
`mvwifi_history.log` truncating to 0 bytes: all four Android wrappers
rotated via a *shared* `$HIST.tmp` — concurrent wrappers (both nudge
tasks fire in the same second) raced, and a second `>` truncate +
first `mv` could install an empty file. Now an atomic `mkdir` lock
plus per-PID tmp names; losers skip rotation until the next run.

### Field note (2026-10-08)
The Tasker import saga's actual root cause: Tasker keeps project
state in memory and persists only on a **graceful exit** — a
force-stop/swipe-kill discards the import, so scheduled ticks kept
firing the last *persisted* defs while the GUI showed the imported
ones. Also: deleting a project tab orphans its tasks/profiles
globally, so reimports fail on name collisions. Corrected
procedure (delete tab + leftovers → import → graceful exit →
relaunch) documented in `docs/android-termux-setup.md` and
`docs/troubleshooting.md`; verified — scheduled markers stamp
`gen 3937e7`.

---

## Template for Future Entries

### YYYY-MM-DD - Brief Description

#### Completed
- [ ] Task 1
- [ ] Task 2

#### Technical Decisions
1. Decision with rationale

#### Challenges
- Issue and resolution

#### Testing
- What was tested
- Results

#### Next Steps
- [ ] Next task
