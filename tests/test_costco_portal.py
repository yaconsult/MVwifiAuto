"""Tests for the Costco captive portal handler."""

from unittest.mock import MagicMock, patch

import pytest
from requests import RequestException

from mvwifi_auto.costco_portal import (
    COSTCO_LOGIN_URL,
    COSTCO_POST_DATA,
    COSTCO_SSID,
    CostcoPortalError,
    accept_costco_terms,
    handle_costco_connection,
)


class TestAcceptCostcoTerms:
    """Test accepting Costco WiFi terms."""

    def test_successful_terms_acceptance(self):
        """Test successful terms acceptance with explicit portal host."""
        mock_session = MagicMock()
        mock_post_response = mock_session.post.return_value
        mock_post_response.status_code = 200

        mock_get_response = mock_session.get.return_value
        mock_get_response.status_code = 200
        mock_get_response.text = "success"

        result = accept_costco_terms(portal_host="10.0.0.1:8080", session=mock_session)

        assert result is True
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args.args[0] == f"http://10.0.0.1:8080{COSTCO_LOGIN_URL}"

    def test_post_failure_raises_error(self):
        """Test that a POST failure raises CostcoPortalError."""
        mock_session = MagicMock()
        mock_session.post.side_effect = RequestException("connection failed")

        with pytest.raises(CostcoPortalError, match="Failed to accept"):
            accept_costco_terms(portal_host="10.0.0.1", session=mock_session)

    def test_internet_verification_fails(self):
        """Test when terms accepted but internet verification fails."""
        mock_session = MagicMock()
        mock_post_response = mock_session.post.return_value
        mock_post_response.status_code = 200

        mock_get_response = mock_session.get.return_value
        mock_get_response.status_code = 200
        mock_get_response.text = "not connected"

        result = accept_costco_terms(portal_host="10.0.0.1", session=mock_session)

        assert result is False

    def test_auto_detect_portal_host(self):
        """Test auto-detecting portal host when not provided."""
        mock_session = MagicMock()

        # detect_portal_host calls session.get
        mock_get_response = mock_session.get.return_value
        mock_get_response.url = "http://10.0.0.1:8080/portal/login"
        mock_get_response.status_code = 200
        mock_get_response.text = "success"

        # POST response
        mock_post_response = mock_session.post.return_value
        mock_post_response.status_code = 200

        accept_costco_terms(session=mock_session)

        call_args = mock_session.post.call_args
        assert "10.0.0.1:8080" in call_args.args[0]

    def test_no_portal_host_raises_error(self):
        """Test that error is raised when portal host cannot be detected."""
        mock_session = MagicMock()
        mock_session.get.side_effect = RequestException("no network")

        with pytest.raises(CostcoPortalError, match="portal host"):
            accept_costco_terms(session=mock_session)

    def test_uses_requests_module_when_no_session(self):
        """Test that the requests module is used when no session is provided."""
        with (
            patch("mvwifi_auto.costco_portal.requests") as mock_requests,
            patch("mvwifi_auto.costco_portal.detect_portal_host", return_value="10.0.0.1"),
            patch("mvwifi_auto.costco_portal.verify_internet_connectivity", return_value=True),
        ):
            mock_post_response = mock_requests.post.return_value
            mock_post_response.status_code = 200

            result = accept_costco_terms(portal_host="10.0.0.1")

        assert result is True
        mock_requests.post.assert_called_once()

    def test_post_data_sent_correctly(self):
        """Test that the Costco POST data is sent in the request body."""
        mock_session = MagicMock()
        mock_post_response = mock_session.post.return_value
        mock_post_response.status_code = 200

        mock_get_response = mock_session.get.return_value
        mock_get_response.status_code = 200
        mock_get_response.text = "success"

        accept_costco_terms(portal_host="10.0.0.1", session=mock_session)

        call_kwargs = mock_session.post.call_args.kwargs
        assert call_kwargs["data"] == COSTCO_POST_DATA


class TestHandleCostcoConnection:
    """Test the full Costco connection handler."""

    def test_successful_connection(self):
        """Test successful portal handling."""
        mock_session = MagicMock()

        with (
            patch("mvwifi_auto.costco_portal.detect_portal_host", return_value="10.0.0.1:8080"),
            patch("mvwifi_auto.costco_portal.accept_costco_terms", return_value=True),
        ):
            result = handle_costco_connection(session=mock_session)

        assert result is True

    def test_no_portal_but_has_internet(self):
        """Test when no portal is detected but internet works."""
        mock_session = MagicMock()

        with (
            patch("mvwifi_auto.costco_portal.detect_portal_host", return_value=None),
            patch("mvwifi_auto.costco_portal.verify_internet_connectivity", return_value=True),
        ):
            result = handle_costco_connection(session=mock_session)

        assert result is True

    def test_no_portal_no_internet_retries(self):
        """Test that it retries when no portal and no internet."""
        mock_session = MagicMock()

        with (
            patch("mvwifi_auto.costco_portal.detect_portal_host", return_value=None),
            patch("mvwifi_auto.costco_portal.verify_internet_connectivity", return_value=False),
            patch("mvwifi_auto.costco_portal.time.sleep"),
        ):
            result = handle_costco_connection(
                max_attempts=2, attempt_delay=0.1, session=mock_session
            )

        assert result is False

    def test_portal_acceptance_fails_retries(self):
        """Test that it retries when portal acceptance fails."""
        mock_session = MagicMock()

        with (
            patch("mvwifi_auto.costco_portal.detect_portal_host", return_value="10.0.0.1"),
            patch("mvwifi_auto.costco_portal.accept_costco_terms", return_value=False),
            patch("mvwifi_auto.costco_portal.time.sleep"),
        ):
            result = handle_costco_connection(
                max_attempts=3, attempt_delay=0.1, session=mock_session
            )

        assert result is False

    def test_costco_error_propagates_after_max_attempts(self):
        """Test that CostcoPortalError propagates after max attempts."""
        mock_session = MagicMock()

        with (
            patch("mvwifi_auto.costco_portal.detect_portal_host", return_value="10.0.0.1"),
            patch(
                "mvwifi_auto.costco_portal.accept_costco_terms",
                side_effect=CostcoPortalError("fail"),
            ),
            patch("mvwifi_auto.costco_portal.time.sleep"),
            pytest.raises(CostcoPortalError, match="fail"),
        ):
            handle_costco_connection(max_attempts=2, attempt_delay=0.1, session=mock_session)


class TestConstants:
    """Test that the scaffolded constants are present and documented."""

    def test_costco_ssid_defined(self):
        """Test that the SSID constant exists for future use."""
        assert COSTCO_SSID == "Costco Member Wifi"

    def test_login_url_defined(self):
        """Test that the login URL constant exists (TODO: verify on-site)."""
        assert COSTCO_LOGIN_URL.startswith("/")

    def test_post_data_defined(self):
        """Test that the POST data constant exists (TODO: verify on-site)."""
        assert isinstance(COSTCO_POST_DATA, dict)
        assert len(COSTCO_POST_DATA) > 0
