"""Pytest configuration and fixtures."""

import logging
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_dbus():
    """Mock dbus module for testing."""
    with patch("mvwifi_auto.network_manager.dbus") as mock:
        # Setup common D-Bus mock structure
        mock.Interface = MagicMock()
        mock.SystemBus = MagicMock()
        mock.DBusException = Exception
        yield mock


@pytest.fixture
def mock_network_manager(mock_dbus):
    """Create a NetworkManager instance with mocked D-Bus."""
    from mvwifi_auto.network_manager import NetworkManager

    # Mock the bus and NM object
    mock_bus = MagicMock()
    mock_nm_obj = MagicMock()

    mock_dbus.SystemBus.return_value = mock_bus
    mock_bus.get_object.return_value = mock_nm_obj

    nm = NetworkManager()
    nm._bus = mock_bus
    nm._nm = mock_nm_obj
    nm._nm_interface = MagicMock()

    return nm


@pytest.fixture
def mock_requests():
    """Mock requests library."""
    with patch("mvwifi_auto.captive_portal.requests") as mock:
        yield mock


import subprocess as real_subprocess


@pytest.fixture
def mock_subprocess():
    """Mock subprocess module."""
    with patch("mvwifi_auto.network_manager.subprocess") as mock:
        # Set up real exception classes on the mock
        mock.TimeoutExpired = real_subprocess.TimeoutExpired
        mock.FileNotFoundError = FileNotFoundError
        mock.CalledProcessError = real_subprocess.CalledProcessError
        yield mock


@pytest.fixture
def mock_captive_subprocess():
    """Mock subprocess in captive_portal module."""
    with patch("mvwifi_auto.captive_portal.subprocess") as mock:
        mock.TimeoutExpired = real_subprocess.TimeoutExpired
        mock.FileNotFoundError = FileNotFoundError
        yield mock


@pytest.fixture
def quiet_logging():
    """Set logging to WARNING level for tests."""
    logging.getLogger("mvwifi_auto").setLevel(logging.WARNING)
    yield
    logging.getLogger("mvwifi_auto").setLevel(logging.DEBUG)


@pytest.fixture
def sample_networks():
    """Sample network scan results."""
    return [
        {"ssid": "dd-wrt", "signal": 80, "security": "WPA2", "has_security": True},
        {"ssid": "cmvwifi", "signal": 70, "security": "Open", "has_security": False},
        {"ssid": "RandomNetwork", "signal": 60, "security": "WPA2", "has_security": True},
    ]


@pytest.fixture
def controller(quiet_logging):
    """Create a WiFiController with default settings."""
    from mvwifi_auto.controller import WiFiController

    return WiFiController()
