"""Captive portal handler for Costco WiFi.

Scaffolded module — the actual portal protocol (endpoint path, form
fields, headers) must be captured on-site using the portal analyzer.
See ``docs/costco-portal-capture.md`` for the full runbook::

    mvwifi-analyze-portal --probe-url http://1.1.1.1/ --save-html \
        --html-path ~/storage/shared/costco_portal.html \
        --output ~/storage/shared/costco_portal_report.txt

Once the protocol is known, fill in the constants below and the
existing functions will handle the rest.  The HTTP plumbing (interface
binding, redirect host detection, internet verification) is shared
with :mod:`mvwifi_auto.captive_portal` and works for any portal.

Protocol differences from cmvwifi (expected, to be verified on-site):
- Costco WiFi SSID is typically ``CostcoWiFi`` (verify)
- Portal requires a checkbox acceptance (cmvwifi only has a button)
- POST endpoint and form field names differ
- Portal host is dynamic (same as cmvwifi — extract from redirect)
"""

from __future__ import annotations

import logging
import time

import requests
from requests import RequestException

from mvwifi_auto.captive_portal import (
    DEFAULT_USER_AGENT,
    detect_portal_host,
    verify_internet_connectivity,
)

logger = logging.getLogger("mvwifi_auto.costco_portal")


class CostcoPortalError(Exception):
    """Costco portal operation error."""

    pass


# ---------------------------------------------------------------------------
# TODO: Fill in these constants after capturing the portal structure
# with `mvwifi-analyze-portal` on a Costco WiFi connection.
# ---------------------------------------------------------------------------
# Costco WiFi SSID (verify on-site)
COSTCO_SSID = "CostcoWiFi"

# Portal form endpoint (relative to the portal host).
# Example for cmvwifi: "/forms/guest_toued"
# TODO: Replace with actual Costco endpoint from analyzer output.
COSTCO_LOGIN_URL = "/accept"  # TODO: verify

# Form data for the POST acceptance.
# cmvwifi uses: {"origurl": "http://www.google.com", "ok": "Accept and Continue"}
# Costco may use different field names — check the analyzer output for
# hidden fields, checkbox names, and submit button name/value.
# TODO: Replace with actual Costco form fields from analyzer output.
COSTCO_POST_DATA: dict[str, str] = {
    "accept": "1",  # TODO: verify checkbox field name
    "submit": "Continue",  # TODO: verify submit button name/value
}

# Extra headers for the POST (if Costco requires any beyond the standard
# Content-Type and Referer).  Empty by default.
COSTCO_EXTRA_HEADERS: dict[str, str] = {}


def accept_costco_terms(
    portal_host: str | None = None,
    timeout: int = 10,
    session: requests.Session | None = None,
) -> bool:
    """Accept Costco WiFi terms of service.

    Posts to the captive portal form to accept terms and gain internet
    access.  The portal host is extracted from the redirect URL (same
    approach as cmvwifi).

    Args:
        portal_host: Portal host (IP or IP:port). If None, auto-detected.
        timeout: Request timeout in seconds.
        session: Optional requests session for interface binding.

    Returns:
        True if terms acceptance was successful.

    Raises:
        CostcoPortalError: If the portal host cannot be determined or
            the POST request fails.
    """
    if portal_host is None:
        portal_host = detect_portal_host(timeout=timeout, session=session)
        if portal_host is None:
            raise CostcoPortalError("Could not determine Costco portal host")

    login_url = f"http://{portal_host}{COSTCO_LOGIN_URL}"

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"http://{portal_host}/",
    }
    headers.update(COSTCO_EXTRA_HEADERS)

    post_data = dict(COSTCO_POST_DATA)

    post_func = session.post if session is not None else requests.post

    try:
        response = post_func(
            login_url,
            data=post_data,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )

        if response.status_code in (200, 302, 303):
            time.sleep(1)
            return verify_internet_connectivity(session=session)

        logger.warning("Costco portal POST returned status %d", response.status_code)
        return False

    except RequestException as e:
        raise CostcoPortalError(f"Failed to accept Costco terms: {e}") from e


def handle_costco_connection(
    max_attempts: int = 3,
    attempt_delay: float = 2.0,
    session: requests.Session | None = None,
) -> bool:
    """Handle full Costco WiFi connection including captive portal.

    This function:
    1. Waits for connection to Costco WiFi to be established
    2. Detects the captive portal host
    3. Accepts terms of service
    4. Verifies internet connectivity

    Args:
        max_attempts: Maximum number of captive portal attempts.
        attempt_delay: Delay between attempts in seconds.
        session: Optional requests session for interface binding.

    Returns:
        True if successfully connected with internet access.
    """
    time.sleep(2)

    for attempt in range(1, max_attempts + 1):
        try:
            portal_host = detect_portal_host(session=session)
            if portal_host is None:
                # No portal detected — might already have internet
                if verify_internet_connectivity(session=session):
                    return True
                if attempt < max_attempts:
                    time.sleep(attempt_delay)
                    continue
                return False

            logger.info("Costco portal host: %s", portal_host)

            if accept_costco_terms(portal_host=portal_host, session=session):
                return True

            if attempt < max_attempts:
                time.sleep(attempt_delay)

        except CostcoPortalError:
            if attempt >= max_attempts:
                raise
            time.sleep(attempt_delay)

    return False
