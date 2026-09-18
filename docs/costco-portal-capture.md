# Costco WiFi Portal Capture

How to collect the information needed to finish `costco_portal.py`
and what to do with it afterward.

## Goal

`src/mvwifi_auto/costco_portal.py` is scaffolded: all the HTTP
plumbing works (interface binding, redirect host detection, internet
verification) but the Costco-specific **protocol constants** are TODO:

- Portal POST endpoint path (cmvwifi uses `/forms/guest_toued`)
- Form field names and values (cmvwifi uses `origurl` + `ok`)
- **Checkbox field name/value** — Costco requires checking a box to
  accept conditions, unlike cmvwifi which only has a submit button.
  The POST must include the checkbox field (e.g. `accept=1`) or the
  acceptance will be rejected.
- Required headers (Referer, Content-Type, User-Agent)

## Known So Far (2026-09-17 first visit)

- **SSID**: `Costco Member Wifi` — open network, multiple BSSIDs on
  enterprise APs (NOT `CostcoWiFi`)
- **Portal is JS-rendered** — the probe redirected but the page was
  blank in curl/script. Content loads via JavaScript, so
  `mvwifi-analyze-portal` form parsing finds nothing. The report
  still captures the redirect chain; the **browser dev-tools capture
  is essential** for the actual auth flow
- **Login wants the Costco app / Costco.com account** — likely
  Azure AD B2C OAuth (`signin.costco.com`). This is probably the
  "login-required" pattern, not a simple terms-accept POST
- **Question to answer on-site**: is there a non-app path — e.g.
  membership number field, or browser-based Costco.com login —
  and where does the conditions checkbox sit in the flow?

The capture fills these in.

## Prerequisites

- Physically at a Costco, connected to `CostcoWiFi` (verify SSID —
  update `costco_portal.py` if it differs)

The capture works on **either** device:

- **Laptop (recommended)** — no extra setup; the repo is already
  installed.  Bonus: browser dev tools can watch the real POST when
  you manually accept the portal.
- **Phone (Termux)** — needs Termux set up per
  `docs/android-termux-setup.md` and `termux-setup-storage` run
  previously (for `~/storage/shared/`)

## Capture on the Laptop (easiest)

Everything is scripted — no internet needed on-site:

```bash
cd ~/DevinProjects/MVwifiAuto

# 1. Before connecting: scan for the exact SSID
nmcli device wifi list | grep -i costco

# 2. Connect to it
nmcli device wifi connect CostcoWiFi

# 3. Run the capture (do NOT accept the portal yet)
./scripts/capture_portal.sh
```

This creates `portal_capture_<timestamp>/` containing:

- `report.txt` — parsed portal structure (forms, fields, buttons)
- `portal.html` — raw portal page HTML
- `probe_curl.txt` / `probe_body.html` — raw redirect response
- `portal_follow.html` / `follow_curl.txt` — full redirect chain
- `wifi_scan.txt`, `connected_ssid.txt`, `device_status.txt`

Then:

```bash
# 4. Walk the login flow in a browser — two ways to do this:
#
#    a) Automated (recommended): Playwright recorder script.
#       One-time setup at home (downloads a browser, ~300MB):
#         uv run --with playwright playwright install chromium
#       Then on-site:
#         ./scripts/capture_portal_browser.py
#       It opens a visible browser, records a HAR + rendered DOM +
#       screenshot for every page, and keeps recording while you
#       complete the login manually. Close the window to finish.
#
#    b) Manual: dev tools — see the detailed "Dev Tools Capture"
#       section below.

# 5. Verify internet now works
./scripts/capture_portal.sh --post
```

## Dev Tools Capture (detailed)

The portal page is a JS shell — curl sees a blank page. Everything
that matters happens in the Network tab. (Skip this section if you
used `capture_portal_browser.py` — it records the same data
automatically: HAR, rendered DOM, screenshots, nav log.)

### Setup (do this BEFORE triggering the portal)

1. Connect to `Costco Member Wifi` — do NOT accept anything yet
2. Open Firefox or Chrome → press **F12** → **Network** tab
3. Enable two settings:
   - **"Persist Logs"** (Firefox, gear menu) / **"Preserve log"**
     (Chrome, top toolbar) — keeps requests across page redirects.
     Without this, the log wipes on every redirect and you lose the
     chain
   - **"Disable cache"** — forces fresh responses so nothing is
     served from cache
4. Widen the dev-tools pane so you can see full URLs

### Trigger the portal

In the same browser, visit a **plain HTTP** URL (HTTPS won't
redirect):

```
http://neverssl.com/
```

(or `http://1.1.1.1/`, or `http://detectportal.firefox.com/canonical.html`)

### Follow the redirect chain

Every row in the Network tab is one request. Click each one and
check the **Headers** pane:

- **Status 301/302/303/307** → look at the `Location:` **response**
  header — that's the next hop. Follow it in the next rows
- **Status 200** → a real page loaded (portal page, login page)
- Note every domain you pass through. Specifically watch for:
  - `signin.costco.com`, `*.b2clogin.com`,
    `login.microsoftonline.com` → **Azure AD B2C OAuth**
    (login-required pattern, hard to automate)
  - A SASE/portal-vendor domain (e.g. Nile, Meter, Meraki,
    Aruba/ClearPass) → enterprise portal, maybe POST-replayable
  - `costco.com` paths → Costco-hosted login page

### Find the auth mechanism

Once the login screen renders:

- Use the **Fetch/XHR** filter button (top of Network tab) — this
  shows API calls the JS makes, which is where the real protocol
  lives on a JS portal
- Note what the page asks for: Costco app? Email+password?
  Membership number? Look for a **"continue in browser"** or
  small non-app link — if one exists, the flow may be automatable
- Screenshot each screen (they're small and easy to lose track of)

### Watch the submission

If you reach a form (checkbox + button, or member-number field):

1. Check the conditions box, click Accept/Continue
2. Find the **POST** that goes out in the Network tab (usually the
   first POST after the click)
3. Click it → **Headers** pane: record method, full URL,
   `Content-Type`, `Referer`, `Origin`
4. **Request/Payload** pane (Firefox: "Request"; Chrome: "Payload"):
   record EVERY field name and value — hidden fields, the checkbox
   name/value, the button name/value. These become `COSTCO_POST_DATA`
5. Check the **Response**: does it return a token, set a cookie, or
   redirect to a success/callback URL? A callback URL on the portal
   host with a token parameter is often what actually authorizes
   the device's MAC — capture that request too

### Save everything

- **HAR file** (the gold standard): right-click anywhere in the
  Network tab request list → **"Save All As HAR"** (Firefox:
  gear menu → Save All As HAR; Chrome: right-click → Save all as
  HAR with content). This records every request, response,
  header, and body — shareable and replayable later
- **Copy as cURL**: right-click the key POST → Copy → Copy as cURL
  → paste into a file in the capture dir. Instant replay command
- **Cookies**: dev tools → Storage/Application tab → Cookies →
  note anything the portal set (session tokens)

### What decides the outcome

- **Simple POST to the portal host** (fields incl. checkbox +
  button, then internet works) → POST-replayable, fill in
  `costco_portal.py` constants
- **OAuth chain** (B2C domains, app deep-link, token redirects)
  → not POST-replayable; pivot to "auto-connect + notify" design
- **Either way**: after success, note whether reconnecting later
  skips the login (MAC remembered = long session = manual login
  covers many visits)

## Capture on the Phone (Termux)

Run in Termux while connected to Costco WiFi:

```bash
mvwifi-analyze-portal \
    --probe-url http://1.1.1.1/ \
    --save-html \
    --html-path ~/storage/shared/costco_portal.html \
    --output ~/storage/shared/costco_portal_report.txt
```

Notes:

- `--probe-url http://1.1.1.1/` — any HTTP (not HTTPS) URL triggers the
  portal redirect. `detectportal.firefox.com/canonical.html` also works.
- `--save-html` saves the raw portal page — needed if the report misses
  fields the parser doesn't recognize.
- `--html-path` — **required on Termux**: the default `/tmp/portal.html`
  is not writable from Termux.
- `--interface wlan0` — add this if cellular is on and requests route
  over cellular instead of Costco WiFi.

## What you get

- **Laptop**: a `portal_capture_<timestamp>/` directory in the repo
  (listed above)
- **Phone**: two files in `~/storage/shared/` (pull via `adb pull`,
  Drive, or `cat`): `costco_portal_report.txt` (parsed structure)
  and `costco_portal.html` (raw page)

## What to do with the report

**Caution**: since the Costco portal is JS-rendered, the analyzer
report may only show the redirect chain — the real protocol comes
from the dev-tools capture. Two outcomes:

**If a simple POST exists** (member number field, checkbox, button):

Open `src/mvwifi_auto/costco_portal.py` and fill in the constants at
the top of the file:

1. **POST endpoint** — from the final POST in dev tools
2. **Form fields** — every field name/value the POST submits
3. **Checkbox** — the checkbox field name/value must be in
   `COSTCO_POST_DATA` (scaffold has `"accept": "1"` placeholder)
4. **Button label** — the submit button's `value` if required
5. **SSID** — done: `Costco Member Wifi` (already corrected)

**If it's OAuth/app-required** (redirect chain hits
`signin.costco.com` / Azure B2C, or demands the app): a POST-replay
handler can't work. The realistic Android flow becomes
"auto-connect + notify to sign in" (WiFi Near → connect → detect
portal → notify), plus check whether Costco authorizes the device
for a long session so one manual login covers many visits.

Then update `tests/test_costco_portal.py` expectations to match, run:

```bash
uv run pytest tests/test_costco_portal.py -v
```

## Verify on-site

Once constants are filled in, test live before leaving:

```bash
# Phone (Termux):
mvwifi-android --once --verbose

# Laptop — quick check that the portal is gone:
curl -s -o /dev/null -w '%{http_code}\n' \
    http://detectportal.firefox.com/success.txt   # want: 200
```

Or POST manually to sanity-check first:

```bash
curl -v -X POST "http://<portal_host>/<endpoint>" \
    -d "field1=value1" -d "field2=value2"
```

Success = the report shows internet verification passing.

## If the portal doesn't appear

- Phone: make sure you're actually on Costco WiFi, not cellular
  (`--interface wlan0` forces WiFi)
- Laptop: disconnect ethernet/dock so WiFi is the only route
- The portal may only appear for new/expired sessions — toggle WiFi
  off/on or forget+rejoin the network to force re-detection
- Try different probe URLs: `http://1.1.1.1/`, `http://neverssl.com/`,
  `http://detectportal.firefox.com/canonical.html`
