"""Tests for captive portal handling."""

import pytest

from mvwifi_auto.captive_portal import (
    DEFAULT_USER_AGENT,
    CMVWIFI_LOGIN_URL,
    CaptivePortalError,
    accept_cmvwifi_terms,
    detect_captive_portal,
    get_default_gateway,
    verify_internet_connectivity,
)


class TestGetDefaultGateway:
    """Test gateway detection."""

    def test_successful_gateway_detection(self, mock_captive_subprocess):
        """Test detecting gateway from ip route output."""
        mock_result = mock_captive_subprocess.run.return_value
        mock_result.returncode = 0
        mock_result.stdout = "default via 192.168.1.1 dev wlp3s0 proto dhcp metric 600"

        gateway = get_default_gateway()

        assert gateway == "192.168.1.1"
        mock_captive_subprocess.run.assert_called_once()

    def test_no_gateway_found(self, mock_captive_subprocess):
        """Test when no default route exists."""
        mock_result = mock_captive_subprocess.run.return_value
        mock_result.returncode = 0
        mock_result.stdout = ""

        gateway = get_default_gateway()

        assert gateway is None

    def test_command_failure(self, mock_captive_subprocess):
        """Test when ip command fails."""
        mock_captive_subprocess.run.side_effect = FileNotFoundError()

        gateway = get_default_gateway()

        assert gateway is None


class TestDetectCaptivePortal:
    """Test captive portal detection."""

    def test_no_portal_success_response(self, mock_requests):
        """Test when no portal (200 response with success)."""
        mock_response = mock_requests.get.return_value
        mock_response.status_code = 200
        mock_response.text = "success"

        is_captive, redirect = detect_captive_portal()

        assert is_captive is False
        assert redirect is None

    def test_portal_detected_via_redirect(self, mock_requests):
        """Test portal detection via redirect."""
        mock_response = mock_requests.get.return_value
        mock_response.status_code = 302
        mock_response.headers = {"Location": "http://192.168.1.1/login"}

        is_captive, redirect = detect_captive_portal()

        assert is_captive is True
        assert redirect == "http://192.168.1.1/login"

    def test_portal_detected_via_html_response(self, mock_requests):
        """Test portal detection via HTML response."""
        mock_response = mock_requests.get.return_value
        mock_response.status_code = 200
        mock_response.text = "<html><body>Login Required</body></html>"

        is_captive, redirect = detect_captive_portal()

        assert is_captive is True

    def test_uses_correct_user_agent(self, mock_requests):
        """Test that correct User-Agent is sent."""
        detect_captive_portal()

        call_args = mock_requests.get.call_args
        headers = call_args.kwargs.get("headers", {})
        assert headers.get("User-Agent") == DEFAULT_USER_AGENT

    def test_connection_error_indicates_captive(self, mock_requests):
        """Test that connection error suggests captive portal."""
        from requests import ConnectionError

        mock_requests.get.side_effect = ConnectionError()

        is_captive, redirect = detect_captive_portal()

        assert is_captive is True


class TestAcceptCmvwifiTerms:
    """Test accepting Mountain View WiFi terms."""

    def test_successful_terms_acceptance(self, mock_requests):
        """Test successful terms acceptance."""
        # First response for POST
        mock_post_response = mock_requests.post.return_value
        mock_post_response.status_code = 200

        # Second response for verification
        mock_get_response = mock_requests.get.return_value
        mock_get_response.status_code = 200
        mock_get_response.text = "success"

        result = accept_cmvwifi_terms(gateway_ip="192.168.1.1")

        assert result is True
        mock_requests.post.assert_called_once()

        # Check POST URL
        call_args = mock_requests.post.call_args
        assert call_args.args[0] == f"http://192.168.1.1{CMVWIFI_LOGIN_URL}"

    def test_post_failure(self, mock_requests):
        """Test when POST to portal fails."""
        from requests import RequestException

        mock_requests.post.side_effect = RequestException("Connection failed")

        with pytest.raises(CaptivePortalError):
            accept_cmvwifi_terms(gateway_ip="192.168.1.1")

    def test_internet_verification_fails(self, mock_requests):
        """Test when terms accepted but internet verification fails."""
        mock_post_response = mock_requests.post.return_value
        mock_post_response.status_code = 200

        mock_get_response = mock_requests.get.return_value
        mock_get_response.status_code = 200
        mock_get_response.text = "not success"  # Wrong content

        result = accept_cmvwifi_terms(gateway_ip="192.168.1.1")

        assert result is False

    def test_auto_detect_gateway(self, mock_requests, mock_captive_subprocess):
        """Test auto-detecting gateway when not provided."""
        mock_result = mock_captive_subprocess.run.return_value
        mock_result.returncode = 0
        mock_result.stdout = "default via 10.0.0.1 dev eth0"

        mock_post_response = mock_requests.post.return_value
        mock_post_response.status_code = 200

        mock_get_response = mock_requests.get.return_value
        mock_get_response.status_code = 200
        mock_get_response.text = "success"

        accept_cmvwifi_terms()

        # Should use auto-detected gateway
        call_args = mock_requests.post.call_args
        assert "10.0.0.1" in call_args.args[0]

    def test_no_gateway_raises_error(self, mock_captive_subprocess):
        """Test that error is raised when gateway cannot be detected."""
        mock_captive_subprocess.run.side_effect = FileNotFoundError()

        with pytest.raises(CaptivePortalError, match="gateway"):
            accept_cmvwifi_terms()


class TestVerifyInternetConnectivity:
    """Test internet connectivity verification."""

    def test_successful_connectivity(self, mock_requests):
        """Test successful connectivity check."""
        mock_response = mock_requests.get.return_value
        mock_response.status_code = 200
        mock_response.text = "success"

        result = verify_internet_connectivity()

        assert result is True

    def test_wrong_status_code(self, mock_requests):
        """Test when status code is not 200."""
        mock_response = mock_requests.get.return_value
        mock_response.status_code = 302
        mock_response.text = "success"

        result = verify_internet_connectivity()

        assert result is False

    def test_wrong_content(self, mock_requests):
        """Test when content doesn't indicate success."""
        mock_response = mock_requests.get.return_value
        mock_response.status_code = 200
        mock_response.text = "Please login"

        result = verify_internet_connectivity()

        assert result is False

    def test_request_exception(self, mock_requests):
        """Test when request fails entirely."""
        from requests import RequestException

        mock_requests.get.side_effect = RequestException("Timeout")

        result = verify_internet_connectivity()

        assert result is False

    def test_uses_firefox_portal_url(self, mock_requests):
        """Test that Firefox portal URL is used by default."""
        verify_internet_connectivity()

        call_args = mock_requests.get.call_args
        assert "firefox.com" in call_args.args[0]
