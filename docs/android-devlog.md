# Android Port Devlog

Development notes for the Tasker-based Android port of MVwifiAuto.

---

## Session 1 — Initial Design

**Goal**: Port MVwifiAuto (Linux/NetworkManager/Python) to rooted Google Pixel using Tasker.

### Key Decisions

- **Platform**: Tasker (already installed with plugins). Rooted with Magisk.
- **No AutoTools**: Initially considered for WiFi scanning, dropped in favour of built-in Tasker actions.
- **No shell commands**: Replaced `ip route` (gateway detection) and `iw dev wlan0 scan` (WiFi scan) with pure Tasker HTTP and WiFi Near approaches.
- **Home WiFi (`dd-wrt`)**: Auto-connects via Android's built-in WiFi auto-connect. Tasker does not need to manage it.
- **cmvwifi only**: Tasker handles `cmvwifi` exclusively — detect, connect, accept portal terms.

### Architecture Chosen

| Component | Implementation |
|-----------|---------------|
| WiFi detection | Tasker **WiFi Near** state profile |
| Connect to cmvwifi | `ConnectToCmvwifi` task → **Net → Connect to WiFi** |
| Captive portal detect | HTTP GET to `detectportal.firefox.com/canonical.html` with **redirects disabled** |
| Gateway IP extraction | Parse `Location:` header from redirect response using Variable Set / Search Replace / Split |
| Portal acceptance | HTTP POST to `http://{gateway}/forms/guest_toued` |
| Internet verify | HTTP GET to `detectportal.firefox.com/success.txt`, check `%http_response_code` = 200 |

### Portal Logic (from `captive_portal.py`)

- Disable redirects → 302/307 response = captive portal present
- `Location:` header contains full redirect URL → extract gateway IP
- POST body: `origurl=http://www.google.com&ok=Accept and Continue`
- POST headers: `Content-Type: application/x-www-form-urlencoded`

---

## Session 2 — Corrections & Refinements

### Issue: Wrong Tasker Actions Referenced
- **Problem**: Guide used outdated Tasker action names ("WiFi Connected", "Scan WiFi Networks").
- **Fix**: Replaced with **WiFi Near** profile (State → Net → WiFi Near) for detection.

### Issue: HTTP Output Variable Names Wrong
- **Problem**: Guide referenced `%ResponseCode`, `%ResponseHeaders` which don't exist.
- **Fix**: Corrected to Tasker's actual local variables set by HTTP Request:
  - `%http_response_code`
  - `%http_headers()`
  - `%http_data`
  - `%http_date`

### Issue: Local Variables Not Visible in Variables Tab
- **Finding**: `%http_response_code` etc. are **local variables** — they only exist during task execution and don't appear in the Variables tab.
- **Workaround**: Add a Flash action immediately after HTTP Request to see values during testing.

### Issue: Portal Detection URL
- **Confirmed**: `http://detectportal.firefox.com/canonical.html` is correct and matches the Python source.  
  When accessed by a browser without a captive portal it may redirect to Mozilla docs, but programmatic requests (Tasker HTTP Request / Python requests) receive the proper 302/200 response.

---

## Session 3 — Debug System

### Added `%DebugMode` Global Variable
- Controls all debug output across all tasks.
- Capital letter (`%DebugMode`) makes it a global persistent variable in Tasker.

### Added `DebugOn` / `DebugOff` Tasks
- Two dedicated tasks to toggle `%DebugMode` between `true` and `false`.
- Each confirms the change with a Flash message.
- Eliminates the need to manually edit any variable.

### Refactored to `DebugFlash` Helper Task
- **Problem**: Every debug message required a 3-action block: `If / Flash / End If`.
- **Solution**: Single `DebugFlash` task receives message via `%par1`, checks `%DebugMode` internally, and flashes only if true.
- **Usage from any task**: `Perform Task [ Name:DebugFlash Par1:your message ]`
- **Result**: All debug output is one action per call site. Turning debug on/off is still one global variable.

#### Task size comparison after refactor

| Task | Before | After |
|------|--------|-------|
| `HandlePortal` | 30 actions | 15 actions |
| `ConnectToCmvwifi` | 9 actions | 5 actions |
| `TestWiFiScan` | 17 actions | 9 actions |

### Added `TestWiFiScan` Task (Home Testing)
- **Problem**: No access to `cmvwifi` at home to test the full flow.
- **Solution**: `TestWiFiScan` task tests WiFi detection using home network (`dd-wrt`):
  1. Reads current SSID from `%WIFII`
  2. Calls `DebugFlash` to show current network
  3. If on `dd-wrt`, confirms detection works and stops
  4. If not on `dd-wrt`, performs WiFi scan and shows results

---

## Session 4 — Documentation Clarity

### Issue: Tasker If Block Mechanics Not Explained
- **Problem**: Instructions didn't explain how to select the If type or where actions go relative to If/End If.
- **Fix**: Added "How Tasker If Blocks Work" callout block explaining:
  - When prompted, select **"If"** for simple blocks, **"If / Else / End If"** when an Else branch is needed
  - Actions added after **If** go *inside* the block until **End If** is added
  - Actions after **End If** run unconditionally (outside the block)
  - Tasker visually indents inside actions

### Added Inside/Outside Markers to Every Action
- Each action now states explicitly: *"Inside outer If block"*, *"Outside any block — always runs"*, *"Back outside all blocks"* etc.
- Skip references updated to correct action numbers as structure changed.

---

## Task Inventory

| Task | Purpose | Calls |
|------|---------|-------|
| `DebugFlash` | Shared logging helper | — |
| `DebugOn` | Set `%DebugMode` = true | — |
| `DebugOff` | Set `%DebugMode` = false | — |
| `HandlePortal` | Detect captive portal, POST acceptance, verify internet | `DebugFlash` |
| `ConnectToCmvwifi` | Connect to cmvwifi, wait, call portal handler | `DebugFlash`, `HandlePortal` |
| `TestWiFiScan` | Home testing — verify WiFi detection without cmvwifi | `DebugFlash` |

## Profile Inventory

| Profile | Trigger | Task |
|---------|---------|------|
| `cmvwifi Auto Connect` | State: WiFi Near SSID=cmvwifi | `ConnectToCmvwifi` |

---

## Session 5 — Clarifications & Guide Polish

### Formatting Convention Note Added
- **Question**: When the guide shows a value in backticks, do you type the backticks?
- **Answer**: No. Backticks are documentation formatting only. Type exactly the characters inside them, nothing else.
- **Fix**: Added "How to Read This Guide" callout at the top of `tasker-android-setup.md` with examples.

### `%par1` Mechanics Clarified
- **Question**: Is the actual content of Parameter 1 the text `%par1`?
- **Answer**: No. In the *calling* task you type the actual message string into the Parameter 1 field. Tasker automatically makes that string available as `%par1` inside the called task (`DebugFlash`). The Flash action inside `DebugFlash` uses `%par1` as its Text value, which Tasker substitutes at runtime.

### `DebugFlash` Always Runs — By Design
- **Question**: Doesn't calling `DebugFlash` always execute even when debug is off?
- **Answer**: Yes, the `Perform Task` action always fires, but `DebugFlash` itself does nothing if `%DebugMode` is not `true`. The `If %DebugMode` check lives inside the helper. Trivial overhead, correct behaviour.

### Variable Split Indexed Array Behaviour Documented
- **Question**: Why does the guide use `%LocationHeader1` instead of `%LocationHeader` after the split?
- **Answer**: `Variable Split` replaces the original variable with an indexed array: `%LocationHeader1`, `%LocationHeader2`, etc. The original `%LocationHeader` no longer holds the full string after the split. Index `1` is the segment before the first `/`, which is the gateway IP.
- **Fix**: Added a callout note directly after Action 8 in `tasker-android-setup.md` explaining this behaviour.

---

## Session 6 — WiFi Connection Failure (Resolved)

### Issue: Connect to WiFi Action Fails with Error 1
- **Symptom**: Error 1, notification saying *"Can't connect to WiFi — please contact the developer"*.
- **Initial theory**: Android 10+ restriction on programmatic WiFi switching.
- **Apparent fix at the time**: Connecting manually + reboot seemed to resolve it, so root cause was incorrectly attributed to a missing saved network.
- **Actual root cause** (confirmed next session): Android 10+ permanently removed `WifiManager.enableNetwork()` — the API Tasker's built-in **Net → Connect to WiFi** relies on. The reboot fix was coincidental or temporary.
- **Real fix**: Replace **Net → Connect to WiFi** with **Code → Run Shell**: `cmd wifi connect-network cmvwifi open` with **Use Root: On**. This uses Android's `cmd wifi` tool directly via root, bypassing the broken API.

### Clarifications Learned This Session
- Tasker's "check notification" error → pull down Android notification shade immediately after the task runs
- Generic "contact the developer" notification = Android OS rejected the request without a specific reason — check prerequisites before assuming a code fix is needed

---

## Session 7 — Real Device Testing & Documentation Hardening

### Tasker If Block Type Selection
- **Discovery**: When adding an If action, Tasker prompts you to choose a type. Must select **"If"** for a simple conditional, or **"If / Else / End If"** when an Else branch is needed. Guide updated with explicit step and callout.
- Actions go *inside* the block (Tasker visually indents them) until End If is added. Actions after End If are outside the block.

### Headers Field is a Plain Text Field
- **Discovery**: Tasker's HTTP Request **Headers** field is a single text field, not a list with an Add button.
- **Fix**: Guide corrected from `Tap Add → Name/Value` to just `Content-Type:application/x-www-form-urlencoded` typed directly.

### Body Field — No Code Fences
- **Discovery**: Guide was showing the POST body in a markdown code block (triple backticks), causing confusion about whether to type them.
- **Fix**: Changed to inline backtick format consistent with every other field. User types only the value, never any surrounding punctuation.

### Backtick Formatting Convention
- **Discovery**: User was unsure whether backticks in the guide were meant to be typed.
- **Fix**: Added "How to Read This Guide" callout at the top of `tasker-android-setup.md`: backticks are formatting only, never typed.

### `%par1` — Parameter Passing to Called Tasks
- **Confirmed**: In the *calling* task, Parameter 1 field receives the literal message string. Tasker automatically assigns it to `%par1` inside the called task. The caller never types `%par1`.

### `guest_toued` Endpoint Confirmed
- **Verified** against `captive_portal.py` line 21: `CMVWIFI_LOGIN_URL = "/forms/guest_toued"` — not a typo.

### `%LocationHeader1` After Variable Split
- **Confirmed**: `Variable Split` on `%LocationHeader` using `/` as splitter creates `%LocationHeader1`, `%LocationHeader2`, etc. The original unsuffixed variable no longer holds the full string. Index 1 = the gateway IP (segment before the first `/`).
- **Fix**: Added callout note in guide after Action 8.

### cmvwifi Auto-Connect Must Be OFF
- **Confirmed**: Android's auto-connect cannot accept captive portal terms — it would connect to `cmvwifi` but leave the phone with no internet.
- Tasker's WiFi Near profile + `ConnectToCmvwifi` task is the replacement for auto-connect. It connects *and* accepts the portal in sequence.
- **Prerequisites updated**: Added full explanation of why auto-connect must be off, how to save the network manually first, and why it must be saved at all.

### Connect to WiFi Error 1 — Root Cause Found
- **Symptom**: Error 1, generic "can't connect" notification when running `ConnectToCmvwifi`.
- **Root cause**: `cmvwifi` was not yet saved in Android's WiFi network list (never manually connected).
- **Fix**: Connect to `cmvwifi` once manually via Android Settings → WiFi (accept the portal in the browser), then disable auto-connect. After a reboot, Tasker's **Net → Connect to WiFi** action worked correctly.
- **No code changes required.**

### How to Read Tasker Error Notifications
- When Tasker shows "check notification": pull down Android notification shade immediately after the task runs.
- Generic "contact the developer" message = Android OS rejected the request. Check prerequisites and permissions before assuming a code fix is needed.

---

## Session 8 — XML Project Generation

### Goal
Generate a valid Tasker `.prj.xml` file from the computer so all tasks and the profile can be imported directly into Tasker, eliminating manual UI entry and the risk of typos.

### Research
- Studied real exported `.prj.xml` files from GitHub to confirm parameter tag formats.
- Key action codes confirmed:
  - `37`=If, `38`=End If, `43`=Else, `30`=Wait, `137`=Stop
  - `130`=Perform Task, `123`=Run Shell, `547`=Variable Set
  - `548`=Flash, `590`=Variable Split, `598`=Variable Search Replace
  - `339`=HTTP Request (modern, uses `Bundle sr="arg0"` for metadata)
  - `170`=WiFi Near (State profile)
- HTTP Request (code `339`) parameter mapping:
  - `arg1`: method (0=GET, 1=POST)
  - `arg2`: URL
  - `arg3`: headers (plain string `Key:Value`)
  - `arg4`: body
  - `arg8`: timeout seconds
  - `arg9`: follow redirects (0=on, 1=off)
- Perform Task (code `130`) parameter mapping:
  - `arg0`: task name
  - `arg2`: priority
  - `arg3`: par1 (Parameter 1)
  - `arg6`: stop calling task when done (1=yes)
  - `arg10`: wait for task to finish (1=yes)
- Run Shell (code `123`): `arg0`=command, `arg1`=use root (1=yes)
- Condition operator `2` = equals (`~` in Tasker UI)

### Output
Created `android/MVwifiAuto.prj.xml` containing:
- Profile: `cmvwifi Auto Connect` (WiFi Near SSID=cmvwifi → runs `ConnectToCmvwifi`)
- Tasks: `DebugFlash`, `DebugOn`, `DebugOff`, `HandlePortal`, `ConnectToCmvwifi`, `TestWiFiScan`

### Transfer Method
```
adb push android/MVwifiAuto.prj.xml /sdcard/Tasker/MVwifiAuto.prj.xml
```
Then in Tasker: long-press bottom nav bar → Import Project.

### Caveats
- XML was generated from documentation and real examples, not an actual Tasker export. May need minor corrections after first import attempt.
- Global variables (`%DebugMode`) are not stored in the XML. Run `DebugOn` after import.
- `&` in HTTP POST body is encoded as `&amp;` in XML.

---

## Session 9 — First Import & Bug Fixes

### Tasker Project Namespace — Task Names Are Global
- **Discovery**: Tasker task names must be unique across **all** projects, not just within a single project. A task called `ConnectToCmvwifi` in Base conflicts with one in MVwifiAuto.
- **Resolution**: User deleted all manually-created tasks and profiles from the Base project before importing `MVwifiAuto.prj.xml`. Import succeeded.

### Bug: Profile Triggered Wrong Task
- **Symptom**: After import, the `cmvwifi Auto Connect` profile was set to execute `DebugFlash` instead of `ConnectToCmvwifi`.
- **Root cause**: The XML had `<mid0>10</mid0>` (DebugFlash's ID) instead of `<mid0>50</mid0>` (ConnectToCmvwifi's ID). Typo during XML authoring.
- **Fix**: Corrected `<mid0>` in `android/MVwifiAuto.prj.xml` to `50`. User also fixed it directly in Tasker UI (no reimport needed for existing install).
- **Lesson**: Always verify profile→task linkage after import by checking the PROFILES tab.

### TestWiFiScan Verified Working
- User ran `TestWiFiScan` at home successfully — flash messages appeared confirming:
  - `DebugFlash` task works correctly
  - `%WIFII` variable returns SSID on the Pixel
  - If block logic executes correctly
  - XML action parameter format is valid for simple actions

### Pending Real-World Test
- Full `ConnectToCmvwifi` → `HandlePortal` flow not yet tested (requires being near `cmvwifi`).
- Recommended test sequence with `DebugOn` active:
  1. Run `ConnectToCmvwifi` manually
  2. Watch for flash: `HTTP code: 302` (or 307)
  3. Watch for flash: `Gateway IP: 192.168.x.x`
  4. Watch for flash: `Success: Connected with internet!`

---

## Open Questions / Next Steps

- [x] Confirm `%WIFII` returns SSID correctly on the Pixel — **verified via TestWiFiScan**
- [ ] Test full portal flow near `cmvwifi`: HTTP redirect → gateway IP → POST acceptance → internet verified
- [ ] Confirm `%http_response_code` is 302/307 after portal detection HTTP GET
- [ ] Confirm `Location:` header format matches search/replace pattern (`Location: http://`)
- [ ] Test WiFi Near profile auto-triggers `ConnectToCmvwifi` when walking into range
- [ ] Once working, export the corrected `.prj.xml` from the phone and commit it to replace the hand-authored version
