"""Tests for the Android/Termux entry point."""

from unittest.mock import MagicMock, patch

from mvwifi_auto.android import main, run_once


class TestRunOnce:
    """Test the run_once function."""

    def test_successful_portal_handling(self):
        """Test successful portal handling with WiFi-bound session."""
        mock_session = MagicMock()

        with (
            patch(
                "mvwifi_auto.android.create_wifi_session",
                return_value=mock_session,
            ),
            patch(
                "mvwifi_auto.android.handle_cmvwifi_connection",
                return_value=True,
            ) as mock_handle,
        ):
            result = run_once(interface="wlan0", verbose=False)

        assert result is True
        mock_handle.assert_called_once()
        call_kwargs = mock_handle.call_args.kwargs
        assert call_kwargs["session"] is mock_session

    def test_binding_failure_returns_false(self):
        """Test that interface binding failure returns False."""
        from mvwifi_auto.wifi_binding import InterfaceBindingError

        with patch(
            "mvwifi_auto.android.create_wifi_session",
            side_effect=InterfaceBindingError("no wlan0"),
        ):
            result = run_once(interface="wlan0")

        assert result is False

    def test_portal_handling_failure_returns_false(self):
        """Test that portal handling failure returns False."""
        mock_session = MagicMock()

        with (
            patch(
                "mvwifi_auto.android.create_wifi_session",
                return_value=mock_session,
            ),
            patch(
                "mvwifi_auto.android.handle_cmvwifi_connection",
                return_value=False,
            ),
        ):
            result = run_once(interface="wlan0")

        assert result is False

    def test_custom_interface_passed_through(self):
        """Test that a custom interface is passed to create_wifi_session."""
        mock_session = MagicMock()

        with (
            patch(
                "mvwifi_auto.android.create_wifi_session",
                return_value=mock_session,
            ) as mock_create,
            patch(
                "mvwifi_auto.android.handle_cmvwifi_connection",
                return_value=True,
            ),
        ):
            run_once(interface="wlan1")

        mock_create.assert_called_once_with("wlan1")

    def test_max_attempts_passed_through(self):
        """Test that max_attempts is passed to handle_cmvwifi_connection."""
        mock_session = MagicMock()

        with (
            patch(
                "mvwifi_auto.android.create_wifi_session",
                return_value=mock_session,
            ),
            patch(
                "mvwifi_auto.android.handle_cmvwifi_connection",
                return_value=True,
            ) as mock_handle,
        ):
            run_once(max_portal_attempts=5)

        call_kwargs = mock_handle.call_args.kwargs
        assert call_kwargs["max_attempts"] == 5


class TestMain:
    """Test the CLI entry point."""

    def test_main_success(self):
        """Test that main returns 0 on success."""
        with patch("mvwifi_auto.android.run_once", return_value=True):
            exit_code = main(["--once"])

        assert exit_code == 0

    def test_main_failure(self):
        """Test that main returns 1 on failure."""
        with patch("mvwifi_auto.android.run_once", return_value=False):
            exit_code = main(["--once"])

        assert exit_code == 1

    def test_main_verbose_flag(self):
        """Test that --verbose flag is passed through."""
        with patch("mvwifi_auto.android.run_once", return_value=True) as mock_run:
            main(["--once", "--verbose"])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["verbose"] is True

    def test_main_custom_interface(self):
        """Test that --interface is passed through."""
        with patch("mvwifi_auto.android.run_once", return_value=True) as mock_run:
            main(["--once", "--interface", "wlan1"])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["interface"] == "wlan1"

    def test_main_custom_max_attempts(self):
        """Test that --max-attempts is passed through."""
        with patch("mvwifi_auto.android.run_once", return_value=True) as mock_run:
            main(["--once", "--max-attempts", "5"])

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["max_portal_attempts"] == 5
