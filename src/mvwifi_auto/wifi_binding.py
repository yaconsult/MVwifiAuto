"""Bind HTTP requests to a specific network interface.

On Android, policy routing sends internet-bound traffic over cellular
whenever mobile data is on.  Tasker's HTTP Request has no interface
binding, so the captive portal redirect — which only arrives over WiFi —
is never seen.  ``curl --interface wlan0`` works from the adb shell
because it binds the socket to wlan0's local IP address, bypassing the
policy routing table.

This module provides the same capability for Python ``requests``: an
:class:`InterfaceBoundAdapter` that forces every connection through a
named interface, plus :func:`create_wifi_session` which returns a
ready-to-use ``requests.Session``.

Used by :mod:`mvwifi_auto.android` on Termux to reuse the exact same
portal-handling code that runs on the laptop.
"""

from __future__ import annotations

import fcntl
import logging
import socket
import struct
import subprocess
from typing import TYPE_CHECKING

import requests
from requests.adapters import HTTPAdapter

if TYPE_CHECKING:
    pass

logger = logging.getLogger("mvwifi_auto.wifi_binding")

# SIOCGIFADDR ioctl request number (Linux)
_SIOCGIFADDR = 0x8915

# Common WiFi interface names on Android (ordered by likelihood)
_WIFI_INTERFACE_CANDIDATES = ["wlan0", "wlan1", "wlan2", "wlan"]


class InterfaceBindingError(Exception):
    """Raised when an interface IP cannot be determined."""

    pass


def _get_interface_ip_ioctl(interface: str) -> str | None:
    """Get IPv4 address via SIOCGIFADDR ioctl.

    Args:
        interface: Network interface name.

    Returns:
        IPv4 address string, or None if the ioctl fails.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            packed = fcntl.ioctl(
                sock.fileno(),
                _SIOCGIFADDR,
                struct.pack("256s", interface[:15].encode("utf-8")),
            )
            return socket.inet_ntoa(packed[20:24])
        finally:
            sock.close()
    except OSError:
        return None


def _get_interface_ip_ip_command(interface: str) -> str | None:
    """Get IPv4 address via ``ip addr`` command.

    Args:
        interface: Network interface name.

    Returns:
        IPv4 address string, or None if the command fails.
    """
    try:
        result = subprocess.run(
            ["ip", "-4", "addr", "show", interface],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("inet "):
                    return stripped.split()[1].split("/")[0]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def get_interface_ip(interface: str = "wlan0") -> str:
    """Get the IPv4 address bound to *interface*.

    Uses the ``SIOCGIFADDR`` ioctl (Linux only).  Falls back to parsing
    ``ip addr`` output when ioctl is unavailable (e.g. non-Linux or
    restricted environments).

    Args:
        interface: Network interface name (e.g. ``wlan0``).

    Returns:
        IPv4 address string.

    Raises:
        InterfaceBindingError: If the IP cannot be determined.
    """
    ip = _get_interface_ip_ioctl(interface)
    if ip is not None:
        return ip

    ip = _get_interface_ip_ip_command(interface)
    if ip is not None:
        return ip

    raise InterfaceBindingError(f"Could not determine IPv4 address for interface '{interface}'")


def detect_wifi_interface() -> str:
    """Auto-detect the active WiFi interface.

    Tries common WiFi interface names (wlan0, wlan1, etc.) and returns
    the first one that has an IPv4 address assigned.  On newer Pixel
    devices the WiFi interface may be ``wlan1`` rather than ``wlan0``.

    Returns:
        The name of the active WiFi interface.

    Raises:
        InterfaceBindingError: If no WiFi interface with an IP is found.
    """
    for interface in _WIFI_INTERFACE_CANDIDATES:
        ip = _get_interface_ip_ioctl(interface)
        if ip is not None:
            logger.info("Auto-detected WiFi interface: %s (IP: %s)", interface, ip)
            return interface

    raise InterfaceBindingError(
        "Could not auto-detect WiFi interface. "
        "Tried: " + ", ".join(_WIFI_INTERFACE_CANDIDATES) + ". "
        "Specify one manually with --interface."
    )


class InterfaceBoundAdapter(HTTPAdapter):  # type: ignore[misc]
    """HTTP adapter that binds all sockets to a specific interface.

    Works like ``curl --interface <name>``: the socket source address
    is set to the interface's local IP, which causes the kernel to route
    traffic through that interface regardless of policy routing rules.

    Example::

        session = requests.Session()
        adapter = InterfaceBoundAdapter("wlan0")
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.get("http://1.1.1.1/")  # goes through wlan0
    """

    def __init__(self, interface: str = "wlan0", **kwargs: object) -> None:
        """Initialize the adapter.

        Args:
            interface: Network interface name to bind to.
            **kwargs: Passed through to :class:`HTTPAdapter`.
        """
        self._source_ip = get_interface_ip(interface)
        self._interface = interface
        super().__init__(**kwargs)

    def init_poolmanager(self, *args: object, **kwargs: object) -> None:
        """Inject source_address into the urllib3 pool manager."""
        kwargs["source_address"] = (self._source_ip, 0)
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args: object, **kwargs: object) -> object:
        """Inject source_address into proxy manager connections."""
        kwargs["source_address"] = (self._source_ip, 0)
        return super().proxy_manager_for(*args, **kwargs)

    @property
    def source_ip(self) -> str:
        """The bound source IP address."""
        return self._source_ip

    @property
    def interface(self) -> str:
        """The interface name this adapter is bound to."""
        return self._interface


def create_wifi_session(
    interface: str | None = None,
    max_retries: int = 0,
) -> requests.Session:
    """Create a ``requests.Session`` bound to a WiFi interface.

    All HTTP and HTTPS requests made through the returned session will
    route through the specified network interface, bypassing Android's
    cellular-preferred policy routing.

    Args:
        interface: Network interface name. If None, auto-detects the
            WiFi interface (tries wlan0, wlan1, etc.). Default: None.
        max_retries: Number of retry attempts (default 0).

    Returns:
        A configured ``requests.Session``.

    Raises:
        InterfaceBindingError: If the interface IP cannot be determined.
    """
    if interface is None:
        interface = detect_wifi_interface()

    session = requests.Session()
    retry_kwargs: dict[str, object] = {}
    if max_retries > 0:
        retry_kwargs["max_retries"] = max_retries
    adapter = InterfaceBoundAdapter(interface, **retry_kwargs)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    logger.debug(
        "Created WiFi-bound session on %s (source IP: %s)",
        interface,
        adapter.source_ip,
    )
    return session
