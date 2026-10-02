"""Periodic auto-join nudge for WiFi networks Android deprioritizes.

cmvwifi's captive portal makes Android's network validator report
"no internet" on every join.  That, plus historical DHCP/association
failures, poisons the network's selection score — observed on-device
as ``CMD_UNWANTED_NETWORK``, ``numConsecutiveConnectionFailure``, and
a BSSID blocklist entry.  Android then backs off auto-join, and
screen-off scan throttling means the next retry can be 15-30 minutes
out even though "Auto-connect" is enabled.

This module is the nudge that bypasses that backoff: run periodically
(from a Tasker Time profile via the ``cmvwifi_nudge`` Termux wrapper),
it checks whether the target SSID is visible but unassociated and, if
so, explicitly requests the connection through the rooted ``cmd wifi``
interface.  The existing WiFi Connected profile then handles the
captive portal as usual.

Behaviour:

- Already on a target SSID        -> no-op
- Connected to a different SSID   -> no-op (never disrupts a working
                                     connection)
- WiFi disabled                   -> no-op (the user may have turned
                                     it off deliberately)
- Target absent from scan         -> no-op
- Target visible, not connected   -> ``cmd wifi connect-network``

CLI::

    mvwifi-nudge
    mvwifi-nudge --ssid cmvwifi --ssid "Costco Member Wifi"
    mvwifi-nudge --dry-run --json
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shlex
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from mvwifi_auto.root_shell import find_su, run_root

logger = logging.getLogger("mvwifi_auto.wifi_nudge")

DEFAULT_SSIDS = ["cmvwifi"]

# `cmd wifi status` emits lines like:
#   Wifi is enabled
#   Wifi is connected to "cmvwifi"
#   Wifi is not connected
_STATUS_ENABLED = re.compile(r"Wifi is enabled", re.IGNORECASE)
_STATUS_CONNECTED = re.compile(r'Wifi is connected to "([^"]+)"')

# `cmd wifi list-scan-results` emits a fixed-width table:
#     BSSID              Frequency      RSSI  Age(sec)  SSID   Flags
#   aa:bb:cc:dd:ee:ff       5540        -63    148.587  cmvwifi [ESS]
# The SSID column may be empty (hidden networks) or contain spaces;
# the Flags column always starts with '['.
_SCAN_LINE = re.compile(
    r"^\s*(?P<bssid>(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})\s+"
    r"(?P<freq>\d+)\s+"
    r"(?P<rssi>-?\d+)\s+"
    r"(?P<age>[\d.]+)\s+"
    r"(?P<tail>.*?)\s*$"
)


@dataclass
class WifiStatus:
    """Parsed ``cmd wifi status`` output."""

    enabled: bool
    connected_ssid: str | None


@dataclass
class ScanResult:
    """One row of ``cmd wifi list-scan-results``."""

    bssid: str
    frequency: int
    rssi: int
    ssid: str  # empty for hidden networks


@dataclass
class NudgeReport:
    """Outcome of a nudge run (also the --json/--markdown payload)."""

    action: str
    """Terminal state: already_connected, connected_elsewhere,
    wifi_disabled, target_absent, connect_requested, dry_run,
    no_root, status_failed, scan_failed, or connect_failed."""

    ok: bool
    wifi_enabled: bool = False
    connected_ssid: str | None = None
    targets: list[str] = field(default_factory=list)
    visible_targets: list[str] = field(default_factory=list)
    connect_rc: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the report."""
        return asdict(self)


def parse_wifi_status(text: str) -> WifiStatus:
    """Parse ``cmd wifi status`` output.

    Args:
        text: Raw stdout of ``cmd wifi status``.

    Returns:
        A :class:`WifiStatus` with the enabled flag and the
        currently-connected SSID (None when disconnected).
    """
    enabled = False
    connected: str | None = None
    for line in text.splitlines():
        if _STATUS_ENABLED.search(line):
            enabled = True
        match = _STATUS_CONNECTED.search(line)
        if match:
            connected = match.group(1)
    return WifiStatus(enabled=enabled, connected_ssid=connected)


def parse_scan_results(text: str) -> list[ScanResult]:
    """Parse ``cmd wifi list-scan-results`` output.

    Args:
        text: Raw stdout of ``cmd wifi list-scan-results``.

    Returns:
        A list of :class:`ScanResult`, one per visible BSSID.
    """
    results: list[ScanResult] = []
    for line in text.splitlines():
        match = _SCAN_LINE.match(line)
        if not match:
            continue
        # The SSID column ends where the Flags column's '[' begins.
        ssid = match.group("tail").split("[", 1)[0].strip()
        results.append(
            ScanResult(
                bssid=match.group("bssid"),
                frequency=int(match.group("freq")),
                rssi=int(match.group("rssi")),
                ssid=ssid,
            )
        )
    return results


def _report(
    action: str,
    ok: bool,
    status: WifiStatus | None,
    targets: list[str],
    visible_targets: list[str] | None = None,
    connect_rc: int | None = None,
) -> NudgeReport:
    """Build a NudgeReport, carrying status fields when available."""
    return NudgeReport(
        action=action,
        ok=ok,
        wifi_enabled=status.enabled if status else False,
        connected_ssid=status.connected_ssid if status else None,
        targets=list(targets),
        visible_targets=list(visible_targets or []),
        connect_rc=connect_rc,
    )


def run_nudge(
    su: str,
    targets: list[str],
    settle: float = 3.0,
    dry_run: bool = False,
) -> NudgeReport:
    """Check WiFi state and request a join if a target SSID is visible.

    Args:
        su: Root shell path from :func:`find_su`.
        targets: SSIDs worth nudging (first visible one wins).
        settle: Seconds to wait between ``start-scan`` and reading
            ``list-scan-results``.
        dry_run: Report what would happen without issuing
            ``connect-network``.

    Returns:
        A :class:`NudgeReport` describing what was decided and done.
    """
    rc, out = run_root(su, "cmd wifi status")
    if rc != 0:
        logger.error("cmd wifi status failed (rc=%s): %s", rc, out.strip())
        return _report("status_failed", False, None, targets)
    status = parse_wifi_status(out)
    logger.info(
        "WiFi status: enabled=%s connected=%s", status.enabled, status.connected_ssid
    )

    if not status.enabled:
        return _report("wifi_disabled", True, status, targets)
    if status.connected_ssid in targets:
        return _report("already_connected", True, status, targets)
    if status.connected_ssid is not None:
        # Never pull the device off a working connection.
        return _report("connected_elsewhere", True, status, targets)

    rc, out = run_root(su, "cmd wifi start-scan")
    if rc != 0:
        logger.warning("start-scan failed (rc=%s): %s", rc, out.strip())
    time.sleep(settle)
    rc, out = run_root(su, "cmd wifi list-scan-results")
    if rc != 0:
        logger.error("list-scan-results failed (rc=%s): %s", rc, out.strip())
        return _report("scan_failed", False, status, targets)

    visible = {r.ssid for r in parse_scan_results(out)}
    hits = [t for t in targets if t in visible]
    logger.info("scan: %d targets visible: %s", len(hits), hits or "none")
    if not hits:
        return _report("target_absent", True, status, targets)

    if dry_run:
        return _report(
            "dry_run", True, status, targets, visible_targets=hits
        )

    target = hits[0]
    rc, out = run_root(
        su, f"cmd wifi connect-network {shlex.quote(target)} open"
    )
    logger.info("connect-network %s -> rc=%s %s", target, rc, out.strip())
    if rc != 0:
        return _report(
            "connect_failed", False, status, targets,
            visible_targets=hits, connect_rc=rc,
        )
    return _report(
        "connect_requested", True, status, targets,
        visible_targets=hits, connect_rc=rc,
    )


def format_markdown(report: NudgeReport) -> str:
    """Render a :class:`NudgeReport` as a small Markdown section."""
    lines = [
        "## WiFi Nudge",
        "",
        f"- **action:** {report.action}",
        f"- **ok:** {report.ok}",
        f"- **wifi enabled:** {report.wifi_enabled}",
        f"- **connected ssid:** {report.connected_ssid or '-'}",
        f"- **targets:** {', '.join(report.targets)}",
        f"- **visible targets:** {', '.join(report.visible_targets) or '-'}",
    ]
    if report.connect_rc is not None:
        lines.append(f"- **connect rc:** {report.connect_rc}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments (default: ``sys.argv[1:]``).

    Returns:
        0 for any clean outcome (including no-ops), 2 when root is
        unavailable, 1 when a wifi command itself failed.
    """
    parser = argparse.ArgumentParser(
        description="Nudge Android to join a visible target WiFi network",
    )
    parser.add_argument(
        "--ssid",
        action="append",
        dest="ssids",
        help="Target SSID (repeatable; default: cmvwifi)",
    )
    parser.add_argument(
        "--settle",
        type=float,
        default=3.0,
        metavar="SECS",
        help="Seconds to wait after start-scan (default: 3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the decision without issuing connect-network",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument(
        "--markdown", action="store_true", help="Print Markdown report"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging"
    )
    parser.add_argument(
        "--log-file", help="Also append log output to this file"
    )
    args = parser.parse_args(argv)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if args.log_file:
        handlers.append(logging.FileHandler(args.log_file))
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=handlers,
    )

    targets = args.ssids or DEFAULT_SSIDS
    su = find_su()
    if su is None:
        report = _report("no_root", False, None, targets)
        logger.error("no usable root shell found")
    else:
        report = run_nudge(
            su, targets, settle=args.settle, dry_run=args.dry_run
        )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    elif args.markdown:
        print(format_markdown(report))

    if report.action == "no_root":
        return 2
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
