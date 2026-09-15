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
- [ ] Wire up Tasker integration (Termux:Tasker plugin or Run Shell)
- [ ] Test Tasker WiFi Near profile triggering `mvwifi-android`
- [ ] Run `mvwifi-analyze-portal` on Costco WiFi to capture portal protocol
- [ ] Fill in `costco_portal.py` constants from analyzer output

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
