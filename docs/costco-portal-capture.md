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
# 4. Accept the portal in a browser.
#    IMPORTANT: open dev tools (F12) → Network tab first.
#    Check the conditions box, click Accept, and note the POST:
#    endpoint URL, every field name, and every field value
#    (hidden fields, checkbox name/value, button name/value).

# 5. Verify internet now works
./scripts/capture_portal.sh --post
```

The browser dev-tools POST capture is **ground truth** — if the
analyzer report and the browser disagree, trust the browser.

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

Open `src/mvwifi_auto/costco_portal.py` and fill in the constants at
the top of the file:

1. **POST endpoint** — from the form's `action` attribute in the report
2. **Form fields** — every `<input>` name/value the form submits,
   including hidden fields and checkbox names/values
3. **Checkbox** — Costco requires accepting conditions via a checkbox.
   Find the `<input type="checkbox">` name/value in the report and make
   sure it ends up in `COSTCO_POST_DATA` — the scaffold has
   `"accept": "1"` as a placeholder, verify the real field name
4. **Button label** — the submit button's `value` if the portal
   requires it (cmvwifi sends `ok=Accept and Continue`)
5. **SSID** — verify `CostcoWiFi` or update to whatever the scan shows

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
