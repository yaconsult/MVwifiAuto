# Costco WiFi Portal Capture

How to collect the information needed to finish `costco_portal.py`
and what to do with it afterward.

## Goal

`src/mvwifi_auto/costco_portal.py` is scaffolded: all the HTTP
plumbing works (interface binding, redirect host detection, internet
verification) but the Costco-specific **protocol constants** are TODO:

- Portal POST endpoint path (cmvwifi uses `/forms/guest_toued`)
- Form field names and values (cmvwifi uses `origurl` + `ok`)
- Any required checkboxes or extra fields
- Required headers (Referer, Content-Type, User-Agent)

The capture fills these in.

## Prerequisites

- Physically at a Costco, connected to `CostcoWiFi` (verify SSID —
  update `costco_portal.py` if it differs)
- Termux set up per `docs/android-termux-setup.md`
- `termux-setup-storage` previously run (for `~/storage/shared/`)

If the phone auto-connects and immediately shows "Sign in to network",
that's ideal — the portal is active.

## Capture

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

Two files in shared storage (pull via `adb pull`, Drive, or `cat`):

- `costco_portal_report.txt` — parsed structure: redirect chain,
  portal host, forms, input fields, buttons, checkboxes
- `costco_portal.html` — raw portal page HTML

## What to do with the report

Open `src/mvwifi_auto/costco_portal.py` and fill in the constants at
the top of the file:

1. **POST endpoint** — from the form's `action` attribute in the report
2. **Form fields** — every `<input>` name/value the form submits,
   including hidden fields and checkbox names/values
3. **Button label** — the submit button's `value` if the portal
   requires it (cmvwifi sends `ok=Accept and Continue`)
4. **SSID** — verify `CostcoWiFi` or update to whatever the scan shows

Then update `tests/test_costco_portal.py` expectations to match, run:

```bash
uv run pytest tests/test_costco_portal.py -v
```

## Verify on-site

Once constants are filled in, test live before leaving:

```bash
mvwifi-android --once --verbose
```

Or POST manually to sanity-check first:

```bash
curl -v -X POST "http://<portal_host>/<endpoint>" \
    -d "field1=value1" -d "field2=value2"
```

Success = the report shows internet verification passing.

## If the portal doesn't appear

- Make sure you're actually on Costco WiFi, not cellular
  (`--interface wlan0` forces WiFi)
- The portal may only appear for new/expired sessions — toggle WiFi
  off/on or forget+rejoin the network to force re-detection
- Try different probe URLs: `http://1.1.1.1/`, `http://neverssl.com/`,
  `http://detectportal.firefox.com/canonical.html`
