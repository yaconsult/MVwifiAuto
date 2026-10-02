"""Tests for the cmvwifi auto-join nudge (wifi_nudge.py).

Sample outputs are verbatim captures from `cmd wifi status` and
`cmd wifi list-scan-results` on Android 17.
"""

import json
from unittest.mock import patch

from mvwifi_auto.wifi_nudge import (
    NudgeReport,
    format_markdown,
    main,
    parse_scan_results,
    parse_wifi_status,
    run_nudge,
)

# `cmd wifi status` while associated with cmvwifi (truncated tail).
STATUS_CONNECTED = """\
Wifi is enabled
Wifi scanning is always available
==== ClientModeManager instance: ConcreteClientModeManager{id=598128215 iface=wlan1} ====
Wifi is connected to "cmvwifi"
WifiInfo: SSID: "cmvwifi", BSSID: 94:b3:4f:a3:9e:e0, Supplicant state: COMPLETED
"""

# `cmd wifi status` while connected to a different network.
STATUS_OTHER = """\
Wifi is enabled
Wifi is connected to "dd-wrt_5G"
WifiInfo: SSID: "dd-wrt_5G", Supplicant state: COMPLETED
"""

# `cmd wifi status` while disconnected.
STATUS_DISCONNECTED = """\
Wifi is enabled
Wifi scanning is always available
==== ClientModeManager instance: ConcreteClientModeManager{id=598128215 iface=wlan1} ====
Wifi is not connected
"""

# `cmd wifi status` with the radio off.
STATUS_DISABLED = """\
Wifi is disabled
"""

# `cmd wifi list-scan-results` (real header + rows; hidden-SSID rows
# carry an empty SSID column, "CSA_Staff_Secure" exercises multi-word
# names are absent here but covered by SSID flags splitting).
SCAN_RESULTS = """\
    BSSID              Frequency      RSSI           Age(sec)     SSID                                 Flags
  22:61:b4:19:20:a6       2452        -90            148.587                                      [WPA2-PSK-CCMP-128][ESS]
  94:b3:4f:63:9e:e0       2412        -57            148.587    cmvwifi                           [ESS]
  94:b3:4f:a3:9e:e0       5540        -63            148.587    cmvwifi                           [ESS]
  62:22:32:fd:b3:26       6135        -67            148.587    CSA_Staff_Secure                  [WPA2-EAP/SHA256-CCMP-128][ESS]
  94:b3:4f:62:f8:20       2462        -82            148.587    cmvwifi                           [ESS]
"""


def _fake_run_root(responses: dict[str, tuple[int, str]]):
    """Return a run_root replacement dispatching on the command."""
    def fake(su: str, command: str, timeout: int = 30):
        for key, response in responses.items():
            if key in command:
                return response
        return (1, f"unexpected command: {command}")

    return fake


class TestParseWifiStatus:
    """Test `cmd wifi status` parsing."""

    def test_connected(self):
        status = parse_wifi_status(STATUS_CONNECTED)
        assert status.enabled is True
        assert status.connected_ssid == "cmvwifi"

    def test_connected_other(self):
        status = parse_wifi_status(STATUS_OTHER)
        assert status.connected_ssid == "dd-wrt_5G"

    def test_disconnected(self):
        status = parse_wifi_status(STATUS_DISCONNECTED)
        assert status.enabled is True
        assert status.connected_ssid is None

    def test_disabled(self):
        status = parse_wifi_status(STATUS_DISABLED)
        assert status.enabled is False
        assert status.connected_ssid is None

    def test_garbage(self):
        status = parse_wifi_status("")
        assert status.enabled is False
        assert status.connected_ssid is None


class TestParseScanResults:
    """Test `cmd wifi list-scan-results` parsing."""

    def test_rows_parsed(self):
        results = parse_scan_results(SCAN_RESULTS)
        assert len(results) == 5
        assert results[1].ssid == "cmvwifi"
        assert results[1].bssid == "94:b3:4f:63:9e:e0"
        assert results[1].frequency == 2412
        assert results[1].rssi == -57

    def test_hidden_ssid_empty(self):
        results = parse_scan_results(SCAN_RESULTS)
        assert results[0].ssid == ""

    def test_ssids_set(self):
        ssids = {r.ssid for r in parse_scan_results(SCAN_RESULTS)}
        assert "cmvwifi" in ssids
        assert "CSA_Staff_Secure" in ssids

    def test_header_and_garbage_skipped(self):
        assert parse_scan_results("BSSID Frequency RSSI\nhello world\n") == []
        assert parse_scan_results("") == []


class TestRunNudge:
    """Test the nudge decision flow (run_root mocked)."""

    def test_noop_when_already_on_target(self):
        with patch(
            "mvwifi_auto.wifi_nudge.run_root",
            side_effect=_fake_run_root({"status": (0, STATUS_CONNECTED)}),
        ):
            report = run_nudge("su", ["cmvwifi"], settle=0)
        assert report.action == "already_connected"
        assert report.ok is True

    def test_noop_when_connected_elsewhere(self):
        commands: list[str] = []

        def fake(su, command, timeout=30):
            commands.append(command)
            if "status" in command:
                return (0, STATUS_OTHER)
            return (1, "must not be called")

        with patch("mvwifi_auto.wifi_nudge.run_root", side_effect=fake):
            report = run_nudge("su", ["cmvwifi"], settle=0)
        assert report.action == "connected_elsewhere"
        assert report.ok is True
        # No scan, and definitely no connect attempt.
        assert all("scan" not in c for c in commands)
        assert all("connect-network" not in c for c in commands)

    def test_noop_when_wifi_disabled(self):
        with patch(
            "mvwifi_auto.wifi_nudge.run_root",
            side_effect=_fake_run_root({"status": (0, STATUS_DISABLED)}),
        ):
            report = run_nudge("su", ["cmvwifi"], settle=0)
        assert report.action == "wifi_disabled"
        assert report.ok is True

    def test_noop_when_target_absent(self):
        scan_no_target = SCAN_RESULTS.replace("cmvwifi", "other_ssid")
        with (
            patch(
                "mvwifi_auto.wifi_nudge.run_root",
                side_effect=_fake_run_root(
                    {
                        "status": (0, STATUS_DISCONNECTED),
                        "start-scan": (0, ""),
                        "list-scan-results": (0, scan_no_target),
                    }
                ),
            ),
            patch("mvwifi_auto.wifi_nudge.time.sleep"),
        ):
            report = run_nudge("su", ["cmvwifi"], settle=0)
        assert report.action == "target_absent"
        assert report.ok is True
        assert report.visible_targets == []

    def test_connects_when_target_visible(self):
        commands: list[str] = []

        def fake(su, command, timeout=30):
            commands.append(command)
            if "status" in command:
                return (0, STATUS_DISCONNECTED)
            if "start-scan" in command:
                return (0, "")
            if "list-scan-results" in command:
                return (0, SCAN_RESULTS)
            if "connect-network" in command:
                return (0, "")
            return (1, "unexpected")

        with (
            patch("mvwifi_auto.wifi_nudge.run_root", side_effect=fake),
            patch("mvwifi_auto.wifi_nudge.time.sleep"),
        ):
            report = run_nudge("su", ["cmvwifi"], settle=0)
        assert report.action == "connect_requested"
        assert report.ok is True
        assert report.connect_rc == 0
        assert "cmd wifi connect-network cmvwifi open" in commands

    def test_dry_run_skips_connect(self):
        commands: list[str] = []

        def fake(su, command, timeout=30):
            commands.append(command)
            if "status" in command:
                return (0, STATUS_DISCONNECTED)
            if "list-scan-results" in command:
                return (0, SCAN_RESULTS)
            return (0, "")

        with (
            patch("mvwifi_auto.wifi_nudge.run_root", side_effect=fake),
            patch("mvwifi_auto.wifi_nudge.time.sleep"),
        ):
            report = run_nudge("su", ["cmvwifi"], settle=0, dry_run=True)
        assert report.action == "dry_run"
        assert report.visible_targets == ["cmvwifi"]
        assert all("connect-network" not in c for c in commands)

    def test_multi_word_ssid_quoted(self):
        commands: list[str] = []
        scan = SCAN_RESULTS.replace("cmvwifi", "Costco Member Wifi")

        def fake(su, command, timeout=30):
            commands.append(command)
            if "status" in command:
                return (0, STATUS_DISCONNECTED)
            if "list-scan-results" in command:
                return (0, scan)
            return (0, "")

        with (
            patch("mvwifi_auto.wifi_nudge.run_root", side_effect=fake),
            patch("mvwifi_auto.wifi_nudge.time.sleep"),
        ):
            report = run_nudge("su", ["Costco Member Wifi"], settle=0)
        assert report.action == "connect_requested"
        assert "cmd wifi connect-network 'Costco Member Wifi' open" in commands

    def test_status_command_failure(self):
        with patch(
            "mvwifi_auto.wifi_nudge.run_root", return_value=(1, "boom")
        ):
            report = run_nudge("su", ["cmvwifi"], settle=0)
        assert report.action == "status_failed"
        assert report.ok is False

    def test_scan_command_failure(self):
        with (
            patch(
                "mvwifi_auto.wifi_nudge.run_root",
                side_effect=_fake_run_root(
                    {
                        "status": (0, STATUS_DISCONNECTED),
                        "list-scan-results": (1, "denied"),
                    }
                ),
            ),
            patch("mvwifi_auto.wifi_nudge.time.sleep"),
        ):
            report = run_nudge("su", ["cmvwifi"], settle=0)
        assert report.action == "scan_failed"
        assert report.ok is False

    def test_connect_command_failure(self):
        with (
            patch(
                "mvwifi_auto.wifi_nudge.run_root",
                side_effect=_fake_run_root(
                    {
                        "status": (0, STATUS_DISCONNECTED),
                        "list-scan-results": (0, SCAN_RESULTS),
                        "connect-network": (1, "rejected"),
                    }
                ),
            ),
            patch("mvwifi_auto.wifi_nudge.time.sleep"),
        ):
            report = run_nudge("su", ["cmvwifi"], settle=0)
        assert report.action == "connect_failed"
        assert report.ok is False
        assert report.connect_rc == 1


class TestCli:
    """Test exit codes and report output modes."""

    def _patch_run(self, responses):
        return patch(
            "mvwifi_auto.wifi_nudge.run_root",
            side_effect=_fake_run_root(responses),
        )

    def test_no_root_exit_2(self):
        with patch("mvwifi_auto.wifi_nudge.find_su", return_value=None):
            assert main([]) == 2

    def test_success_exit_0(self):
        with (
            patch("mvwifi_auto.wifi_nudge.find_su", return_value="su"),
            self._patch_run({"status": (0, STATUS_CONNECTED)}),
        ):
            assert main([]) == 0

    def test_failure_exit_1(self):
        with (
            patch("mvwifi_auto.wifi_nudge.find_su", return_value="su"),
            self._patch_run({"status": (1, "boom")}),
        ):
            assert main([]) == 1

    def test_json_output(self, capsys):
        with (
            patch("mvwifi_auto.wifi_nudge.find_su", return_value="su"),
            self._patch_run({"status": (0, STATUS_CONNECTED)}),
        ):
            assert main(["--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["action"] == "already_connected"
        assert report["ok"] is True
        assert report["connected_ssid"] == "cmvwifi"

    def test_markdown_output(self, capsys):
        with (
            patch("mvwifi_auto.wifi_nudge.find_su", return_value="su"),
            self._patch_run({"status": (0, STATUS_CONNECTED)}),
        ):
            assert main(["--markdown"]) == 0
        out = capsys.readouterr().out
        assert "## WiFi Nudge" in out
        assert "already_connected" in out

    def test_custom_ssid(self, capsys):
        with (
            patch("mvwifi_auto.wifi_nudge.find_su", return_value="su"),
            self._patch_run(
                {
                    "status": (0, STATUS_DISCONNECTED),
                    "list-scan-results": (0, SCAN_RESULTS),
                }
            ),
            patch("mvwifi_auto.wifi_nudge.time.sleep"),
        ):
            # Not in scan results -> target_absent, still exit 0.
            assert main(["--ssid", "NoSuchSSID", "--dry-run"]) == 0
        with (
            patch("mvwifi_auto.wifi_nudge.find_su", return_value="su"),
            self._patch_run(
                {
                    "status": (0, STATUS_DISCONNECTED),
                    "list-scan-results": (0, SCAN_RESULTS),
                }
            ),
            patch("mvwifi_auto.wifi_nudge.time.sleep"),
        ):
            assert main(["--ssid", "cmvwifi", "--dry-run", "--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["action"] == "dry_run"
        assert report["visible_targets"] == ["cmvwifi"]


class TestReport:
    """Test the report renderers."""

    def test_markdown_includes_fields(self):
        report = NudgeReport(
            action="connect_requested",
            ok=True,
            wifi_enabled=True,
            connected_ssid=None,
            targets=["cmvwifi"],
            visible_targets=["cmvwifi"],
            connect_rc=0,
        )
        md = format_markdown(report)
        assert "connect_requested" in md
        assert "cmvwifi" in md
        assert "connect rc" in md

    def test_to_dict_roundtrip(self):
        report = NudgeReport(action="target_absent", ok=True)
        data = report.to_dict()
        assert data["action"] == "target_absent"
        json.dumps(data)  # must be serializable
