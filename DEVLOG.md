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
