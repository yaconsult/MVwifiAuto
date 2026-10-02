"""Tests for the on-device Costco portal capture probe."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from mvwifi_auto.costco_probe import (
    capture_logcat_intents,
    extract_deep_links,
    find_su,
    main,
    run_probe,
)


class TestExtractDeepLinks:
    """Test deep-link extraction from portal HTML/JS."""

    def test_finds_costco_scheme(self):
        html = '<a href="costco://wifi/auth?ssid=abc">open app</a>'
        assert extract_deep_links(html) == ["costco://wifi/auth?ssid=abc"]

    def test_finds_intent_uri(self):
        js = 'window.location = "intent://login#Intent;scheme=costco;end";'
        result = extract_deep_links(js)
        assert result == ["intent://login#Intent;scheme=costco;end"]

    def test_finds_android_app_uri(self):
        html = "android-app://com.costco.app.android/costco/login"
        assert "android-app://com.costco.app.android/costco/login" in extract_deep_links(
            html
        )

    def test_no_links(self):
        assert extract_deep_links("<html><body>hello</body></html>") == []

    def test_deduplicates(self):
        html = 'costco://a costco://a costco://b'
        assert extract_deep_links(html) == ["costco://a", "costco://b"]


class TestFindSu:
    """Test root shell detection."""

    def test_returns_working_candidate(self):
        def fake_run(cmd, **kwargs):
            result = MagicMock()
            if cmd[0] == "su" or cmd[0].startswith("/system"):
                result.returncode = 0
                result.stdout = "0\n"
            else:
                result.returncode = 1
                result.stdout = ""
            return result

        with patch("mvwifi_auto.root_shell.subprocess.run", side_effect=fake_run):
            assert find_su() == "su"

    def test_returns_none_when_unavailable(self):
        with patch(
            "mvwifi_auto.root_shell.subprocess.run", side_effect=OSError("nf")
        ):
            assert find_su() is None


class TestCaptureLogcatIntents:
    """Test the filtered logcat slice."""

    def test_filters_relevant_lines(self, tmp_path: Path):
        logcat = (
            "10-01 12:00:01 I random: noise line\n"
            '10-01 12:00:02 I ActivityTaskManager: START u0 {act=android.intent.action.VIEW dat=costco://wifi cmp=com.costco.app.android/.ui.main.MainActivity}\n'
            "10-01 12:00:03 D other: more noise\n"
        )
        with patch(
            "mvwifi_auto.costco_probe.run_root", return_value=(0, logcat)
        ):
            n = capture_logcat_intents("su", tmp_path)
        assert n == 1
        text = (tmp_path / "intents.txt").read_text()
        assert "dat=costco://wifi" in text
        assert "noise" not in text

    def test_failure_returns_zero(self, tmp_path: Path):
        with patch(
            "mvwifi_auto.costco_probe.run_root", return_value=(1, "")
        ):
            assert capture_logcat_intents("su", tmp_path) == 0


class TestRunProbe:
    """Test the orchestrator with all I/O mocked."""

    def _portal_report(self):
        report = MagicMock()
        report.redirect_url = "http://10.0.0.1/portal?x=1"
        report.portal_host = "10.0.0.1"
        report.error = ""
        report.to_text.return_value = "fake report"
        return report

    def test_full_capture(self, tmp_path: Path):
        html = '<a href="costco://wifi/auth">open</a>'
        # analyze_portal is mocked, so the HTML file it would have
        # written is provided directly.
        (tmp_path / "portal.html").write_text(html)
        with (
            patch(
                "mvwifi_auto.costco_probe.create_wifi_session",
                return_value=MagicMock(),
            ),
            patch(
                "mvwifi_auto.costco_probe.analyze_portal",
                return_value=self._portal_report(),
            ),
            patch(
                "mvwifi_auto.costco_probe.find_su", return_value="su"
            ),
            patch(
                "mvwifi_auto.costco_probe.run_root", return_value=(0, "")
            ) as mock_root,
            patch(
                "mvwifi_auto.costco_probe.launch_portal_page",
                return_value=["ok"],
            ),
            patch(
                "mvwifi_auto.costco_probe.capture_logcat_intents",
                return_value=5,
            ),
            patch("mvwifi_auto.costco_probe.dump_device_state"),
            patch(
                "mvwifi_auto.costco_probe.verify_internet_connectivity",
                return_value=False,
            ),
            patch("mvwifi_auto.costco_probe.time.sleep"),
            patch("mvwifi_auto.costco_probe.fetch_portal_assets", return_value=[]),
        ):
            summary = run_probe(outdir=tmp_path, wait=0)

        assert summary["redirect_url"] == "http://10.0.0.1/portal?x=1"
        assert summary["deep_links"] == ["costco://wifi/auth"]
        assert summary["intent_lines"] == 5
        assert summary["root"] is True
        assert summary["internet_ok"] is False
        mock_root.assert_any_call("su", "logcat -b all -c")
        # Artifacts written
        assert (tmp_path / "summary.json").exists()
        data = json.loads((tmp_path / "summary.json").read_text())
        assert data["portal_host"] == "10.0.0.1"
        assert (tmp_path / "report.md").exists()
        assert (tmp_path / "portal_report.txt").exists()

    def test_bind_failure_returns_error(self, tmp_path: Path):
        from mvwifi_auto.wifi_binding import InterfaceBindingError

        with patch(
            "mvwifi_auto.costco_probe.create_wifi_session",
            side_effect=InterfaceBindingError("no wlan"),
        ):
            summary = run_probe(outdir=tmp_path)
        assert "WiFi bind failed" in summary["error"]
        assert (tmp_path / "summary.json").exists()

    def test_no_redirect_skips_launch(self, tmp_path: Path):
        report = self._portal_report()
        report.redirect_url = ""
        with (
            patch(
                "mvwifi_auto.costco_probe.create_wifi_session",
                return_value=MagicMock(),
            ),
            patch(
                "mvwifi_auto.costco_probe.analyze_portal", return_value=report
            ),
            patch(
                "mvwifi_auto.costco_probe.find_su", return_value="su"
            ),
            patch(
                "mvwifi_auto.costco_probe.launch_portal_page"
            ) as mock_launch,
            patch(
                "mvwifi_auto.costco_probe.verify_internet_connectivity",
                return_value=True,
            ),
        ):
            summary = run_probe(outdir=tmp_path, wait=0)
        mock_launch.assert_not_called()
        assert summary["internet_ok"] is True
        assert "no portal redirect" in summary["note"]

    def test_no_root_skips_logcat(self, tmp_path: Path):
        with (
            patch(
                "mvwifi_auto.costco_probe.create_wifi_session",
                return_value=MagicMock(),
            ),
            patch(
                "mvwifi_auto.costco_probe.analyze_portal",
                return_value=self._portal_report(),
            ),
            patch("mvwifi_auto.costco_probe.find_su", return_value=None),
            patch(
                "mvwifi_auto.costco_probe.launch_portal_page",
                return_value=["ok"],
            ),
            patch(
                "mvwifi_auto.costco_probe.capture_logcat_intents"
            ) as mock_logcat,
            patch(
                "mvwifi_auto.costco_probe.verify_internet_connectivity",
                return_value=False,
            ),
            patch("mvwifi_auto.costco_probe.time.sleep"),
        ):
            summary = run_probe(outdir=tmp_path, wait=0)
        mock_logcat.assert_not_called()
        assert summary["intent_lines"] == 0
        assert "no su" in summary["note"]


class TestMain:
    """Test the CLI entry point."""

    def test_returns_error_code_on_failure(self, tmp_path: Path):
        with patch(
            "mvwifi_auto.costco_probe.run_probe",
            return_value={"error": "WiFi bind failed: x", "outdir": str(tmp_path)},
        ):
            # report.md won't exist; write a stub
            (tmp_path / "report.md").write_text("x")
            rc = main(["--outdir", str(tmp_path), "--json"])
        assert rc == 1

    def test_returns_zero_on_success(self, tmp_path: Path):
        with patch(
            "mvwifi_auto.costco_probe.run_probe",
            return_value={"outdir": str(tmp_path)},
        ):
            (tmp_path / "report.md").write_text("x")
            rc = main(["--outdir", str(tmp_path), "--json"])
        assert rc == 0
