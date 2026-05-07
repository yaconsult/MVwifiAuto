"""Captive portal handler for Mountain View public WiFi (cmvwifi)."""

import re
import subprocess
import time

import requests


class CaptivePortalError(Exception):
    """Captive portal operation error."""

    pass


# User-Agent required for cmvwifi captive portal
DEFAULT_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

# Mountain View WiFi captive portal patterns
CMVWIFI_GATEWAY_PATTERN = re.compile(r"http://(\d+\.\d+\.\d+\.\d+)/")
CMVWIFI_LOGIN_URL = "/forms/guest_toued"


def get_default_gateway() -> str | None:
    """Get the default gateway IP address.

    Returns:
        Gateway IP string or None if cannot determine.
    """
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Parse "default via 192.168.1.1 dev ..."
            match = re.search(r"default\s+via\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
            if match:
                return match.group(1)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def detect_captive_portal(
    test_url: str = "http://detectportal.firefox.com/canonical.html",
    timeout: int = 10,
) -> tuple[bool, str | None]:
    """Detect if we're behind a captive portal.

    Uses the Firefox captive portal detection URL.

    Args:
        test_url: URL to test for captive portal detection.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (is_captive, redirect_url). redirect_url is the captive portal
        page if detected.
    """
    headers = {"User-Agent": DEFAULT_USER_AGENT}

    try:
        # Disable redirects to catch the portal redirect
        response = requests.get(
            test_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )

        # If we get a redirect (302, 307), we're likely behind a captive portal
        if response.status_code in (302, 303, 307):
            redirect_url = response.headers.get("Location", "")
            return True, redirect_url

        # Check if response content is the expected success response
        if response.status_code == 200:
            content = response.text
            # Firefox success marker
            if "success" in content.lower() or "<" not in content:
                return False, None
            # If we got HTML, might be a captive portal
            if "<html" in content.lower():
                return True, test_url

        return False, None

    except requests.Timeout:
        # Timeout might indicate captive portal blocking us
        return True, None
    except requests.ConnectionError:
        # Connection error might indicate no connectivity or portal
        return True, None
    except requests.RequestException:
        return True, None


def accept_cmvwifi_terms(gateway_ip: str | None = None, timeout: int = 10) -> bool:
    """Accept Mountain View WiFi terms of service.

    This posts to the captive portal form to accept terms and gain internet access.

    Args:
        gateway_ip: Gateway IP address. If None, auto-detect.
        timeout: Request timeout in seconds.

    Returns:
        True if terms acceptance was successful.
    """
    if gateway_ip is None:
        gateway_ip = get_default_gateway()
        if gateway_ip is None:
            raise CaptivePortalError("Could not determine gateway IP")

    login_url = f"http://{gateway_ip}{CMVWIFI_LOGIN_URL}"

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": f"http://{gateway_ip}/",
    }

    # Form data based on the micropython captive_portal.py reference
    post_data = {
        "origurl": "http://www.google.com",
        "ok": "Accept and Continue",
    }

    try:
        response = requests.post(
            login_url,
            data=post_data,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )

        # Check for success - usually returns 200 or redirects to success page
        if response.status_code in (200, 302, 303):
            # Verify we now have internet
            time.sleep(1)  # Brief wait for connection to settle
            return verify_internet_connectivity()

        return False

    except requests.RequestException as e:
        raise CaptivePortalError(f"Failed to accept terms: {e}") from e


def verify_internet_connectivity(test_url: str = "http://detectportal.firefox.com/success.txt", timeout: int = 5) -> bool:
    """Verify we have actual internet connectivity.

    Args:
        test_url: URL to test connectivity.
        timeout: Request timeout.

    Returns:
        True if internet is accessible.
    """
    headers = {"User-Agent": DEFAULT_USER_AGENT}

    try:
        response = requests.get(
            test_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )
        # Should get 200 with "success" content if truly connected
        return response.status_code == 200 and "success" in response.text.lower()
    except requests.RequestException:
        return False


def handle_cmvwifi_connection(
    max_attempts: int = 3,
    attempt_delay: float = 2.0,
) -> bool:
    """Handle full cmvwifi connection including captive portal.

    This function:
    1. Waits for connection to cmvwifi to be established
    2. Detects captive portal
    3. Accepts terms of service
    4. Verifies internet connectivity

    Args:
        max_attempts: Maximum number of captive portal attempts.
        attempt_delay: Delay between attempts in seconds.

    Returns:
        True if successfully connected with internet access.
    """
    # Give NetworkManager a moment to fully connect
    time.sleep(2)

    for attempt in range(1, max_attempts + 1):
        try:
            # Check if we need to handle captive portal
            is_captive, redirect_url = detect_captive_portal()

            if not is_captive:
                # Already have internet or no portal needed
                if verify_internet_connectivity():
                    return True
                # No portal but no internet - might need more time
                if attempt < max_attempts:
                    time.sleep(attempt_delay)
                    continue
                return False

            # We have a captive portal - accept terms
            gateway = get_default_gateway()
            if accept_cmvwifi_terms(gateway_ip=gateway):
                return True

            # Failed this attempt, wait and retry
            if attempt < max_attempts:
                time.sleep(attempt_delay)

        except CaptivePortalError:
            if attempt >= max_attempts:
                raise
            time.sleep(attempt_delay)

    return False
