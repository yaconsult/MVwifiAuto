"""Generate Tasker ``.prj.xml`` from Python data structures.

The hand-edited XML in ``android/MVwifiAuto.prj.xml`` was fragile:
parameter-mapping bugs (Sessions 14, 17 of the devlog) were caused by
typos in raw XML that no tool could catch.  This module replaces that
process with testable Python data structures and ElementTree-based
generation.

Usage::

    from mvwifi_auto.tasker_gen import build_mvwifi_project, generate_project_xml

    project = build_mvwifi_project()
    xml_text = generate_project_xml(project)
    Path("android/MVwifiAuto.prj.xml").write_text(xml_text)

Or via the CLI::

    python -m mvwifi_auto.tasker_gen --output android/MVwifiAuto.prj.xml
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from xml.etree.ElementTree import (
    Element,
    SubElement,
    fromstring,
    indent,
    tostring,
)

# ---------------------------------------------------------------------------
# Action codes (from Tasker documentation / empirical exports)
# ---------------------------------------------------------------------------
CODE_IF = 37
CODE_END_IF = 38
CODE_ELSE = 43
CODE_WAIT = 30
CODE_STOP = 137
CODE_PERFORM_TASK = 130
CODE_RUN_SHELL = 123
CODE_VARIABLE_SET = 547
CODE_FLASH = 548
CODE_VARIABLE_SPLIT = 590
CODE_VARIABLE_SEARCH_REPLACE = 598
CODE_HTTP_REQUEST = 339
CODE_CONNECT_WIFI = 398
CODE_WIFI_NEAR_STATE = 170

# Termux:Tasker plugin action code (from official Termux:Tasker template export)
CODE_TERMUX_TASK = 1256900802

# Goto action code
CODE_GOTO = 731

# Condition operator: 2 = equals (~ in Tasker UI)
OP_EQUALS = 2

# Tasker version string for the root element
DEFAULT_TASKER_VERSION = "5.15.14"

# Fixed bundle for HTTP Request (code 339) — Tasker requires this metadata
_HTTP_BUNDLE_XML = (
    '<Vals sr="val">'
    "<net.dinglisch.android.tasker.RELEVANT_VARIABLES>"
    '<StringArray sr=""></StringArray>'
    "</net.dinglisch.android.tasker.RELEVANT_VARIABLES>"
    "<net.dinglisch.android.tasker.RELEVANT_VARIABLES-type>"
    "[Ljava.lang.String;"
    "</net.dinglisch.android.tasker.RELEVANT_VARIABLES-type>"
    "</Vals>"
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class TaskerArg:
    """A single action argument (Str, Int, or Bundle)."""

    index: int
    kind: str  # "Str", "Int", or "Bundle"
    value: str = ""
    ve: str = "3"  # version attribute for Str args

    @classmethod
    def str_arg(cls, index: int, value: str = "", ve: str = "3") -> TaskerArg:
        """Create a string argument."""
        return cls(index=index, kind="Str", value=value, ve=ve)

    @classmethod
    def int_arg(cls, index: int, value: int = 0) -> TaskerArg:
        """Create an integer argument."""
        return cls(index=index, kind="Int", value=str(value))

    @classmethod
    def bundle_arg(cls, index: int, xml_content: str = "") -> TaskerArg:
        """Create a bundle argument (for HTTP Request metadata)."""
        return cls(index=index, kind="Bundle", value=xml_content)


@dataclass
class TaskerCondition:
    """An If-block condition."""

    lhs: str
    op: int
    rhs: str


@dataclass
class TaskerAction:
    """A Tasker action within a task."""

    code: int
    args: list[TaskerArg] = field(default_factory=list)
    conditions: list[TaskerCondition] | None = None
    continue_on_error: bool = False


@dataclass
class TaskerTask:
    """A Tasker task."""

    id: int
    name: str
    priority: int = 2
    actions: list[TaskerAction] = field(default_factory=list)


@dataclass
class TaskerState:
    """A profile state condition (e.g. WiFi Near)."""

    code: int
    args: list[TaskerArg]


@dataclass
class TaskerProfile:
    """A Tasker profile linking a state trigger to a task."""

    id: int
    name: str
    state: TaskerState
    task_id: int


@dataclass
class TaskerProject:
    """A complete Tasker project (root container for import)."""

    name: str
    profiles: list[TaskerProfile]
    tasks: list[TaskerTask]
    tasker_version: str = DEFAULT_TASKER_VERSION


# ---------------------------------------------------------------------------
# XML generation
# ---------------------------------------------------------------------------
def _add_arg(parent: Element, arg: TaskerArg) -> None:
    """Add an argument element to *parent*."""
    if arg.kind == "Str":
        elem = SubElement(
            parent,
            "Str",
            {"sr": f"arg{arg.index}", "ve": arg.ve},
        )
        elem.text = arg.value
    elif arg.kind == "Int":
        SubElement(
            parent,
            "Int",
            {"sr": f"arg{arg.index}", "val": arg.value},
        )
    elif arg.kind == "Bundle":
        bundle = SubElement(parent, "Bundle", {"sr": f"arg{arg.index}"})
        # Parse the bundle XML string and insert it as child elements.
        # If we set it as .text, the XML special characters get escaped
        # (&lt; instead of <), which Tasker cannot parse as nested bundle data.
        try:
            bundle_root = fromstring(arg.value)
            bundle.append(bundle_root)
        except Exception:
            # If for some reason it's not valid XML, keep the original text
            bundle.text = arg.value


def _add_action(task_elem: Element, index: int, action: TaskerAction) -> None:
    """Add an action element to *task_elem*."""
    act = SubElement(task_elem, "Action", {"sr": f"act{index}", "ve": "7"})
    if action.continue_on_error:
        SubElement(act, "con").text = "true"
    SubElement(act, "code").text = str(action.code)

    if action.conditions:
        cond_list = SubElement(act, "ConditionList", {"sr": "if"})
        for ci, cond in enumerate(action.conditions):
            cond_elem = SubElement(cond_list, "Condition", {"sr": f"c{ci}", "ve": "3"})
            SubElement(cond_elem, "lhs").text = cond.lhs
            SubElement(cond_elem, "op").text = str(cond.op)
            SubElement(cond_elem, "rhs").text = cond.rhs

    for arg in action.args:
        _add_arg(act, arg)


def _add_task(root: Element, task: TaskerTask) -> None:
    """Add a task element to *root*."""
    task_elem = SubElement(root, "Task", {"sr": f"task{task.id}"})
    SubElement(task_elem, "id").text = str(task.id)
    SubElement(task_elem, "nme").text = task.name
    SubElement(task_elem, "rty").text = str(task.priority)
    for i, action in enumerate(task.actions):
        _add_action(task_elem, i, action)


def _add_profile(root: Element, profile: TaskerProfile) -> None:
    """Add a profile element to *root*."""
    prof = SubElement(root, "Profile", {"sr": f"prof{profile.id}", "ve": "2"})
    SubElement(prof, "cdate").text = "1000000000000"
    SubElement(prof, "edate").text = "1000000000000"
    SubElement(prof, "id").text = str(profile.id)
    SubElement(prof, "mid0").text = str(profile.task_id)
    SubElement(prof, "nme").text = profile.name

    state = SubElement(prof, "State", {"sr": "con0", "ve": "2"})
    SubElement(state, "code").text = str(profile.state.code)
    for arg in profile.state.args:
        _add_arg(state, arg)


def _add_project(root: Element, project: TaskerProject) -> None:
    """Add the project element to *root*."""
    proj = SubElement(root, "Project", {"sr": "proj0", "ve": "2"})
    SubElement(proj, "name").text = project.name
    SubElement(proj, "pids").text = ",".join(str(p.id) for p in project.profiles)
    SubElement(proj, "tids").text = ",".join(str(t.id) for t in project.tasks)


def generate_project_xml(project: TaskerProject) -> str:
    """Generate the Tasker ``.prj.xml`` file content.

    Args:
        project: The project to serialize.

    Returns:
        XML string suitable for writing to a ``.prj.xml`` file.
    """
    root = Element(
        "TaskerData",
        {"sr": "", "dvi": "1", "tv": project.tasker_version},
    )

    for profile in project.profiles:
        _add_profile(root, profile)

    _add_project(root, project)

    for task in project.tasks:
        _add_task(root, task)

    # Pretty-print with tab indentation (matching Tasker's export format)
    indent(root, space="\t")

    xml_bytes = tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes + "\n"


# ---------------------------------------------------------------------------
# Action builder helpers
# ---------------------------------------------------------------------------
def perform_task(
    name: str,
    par1: str = "",
    stop_after: bool = False,
    wait_for_finish: bool = True,
    priority: int = 0,
) -> TaskerAction:
    """Build a Perform Task (code 130) action."""
    return TaskerAction(
        code=CODE_PERFORM_TASK,
        args=[
            TaskerArg.str_arg(0, name),
            TaskerArg.int_arg(1, priority),
            TaskerArg.str_arg(2, par1),
            TaskerArg.str_arg(3),
            TaskerArg.str_arg(4),
            TaskerArg.str_arg(5),
            TaskerArg.int_arg(6, 1 if stop_after else 0),
            TaskerArg.str_arg(7),
            TaskerArg.int_arg(8, 0),
            TaskerArg.int_arg(9, 0),
            TaskerArg.int_arg(10, 1 if wait_for_finish else 0),
        ],
    )


def flash(text: str) -> TaskerAction:
    """Build a Flash (code 548) action."""
    return TaskerAction(
        code=CODE_FLASH,
        args=[
            TaskerArg.str_arg(0, text),
            TaskerArg.int_arg(1, 0),
        ],
    )


def debug_flash(message: str) -> TaskerAction:
    """Build a Perform Task action that calls DebugFlash."""
    return perform_task("DebugFlash", par1=message, wait_for_finish=True)


def variable_set(name: str, value: str) -> TaskerAction:
    """Build a Variable Set (code 547) action."""
    return TaskerAction(
        code=CODE_VARIABLE_SET,
        args=[
            TaskerArg.str_arg(0, name),
            TaskerArg.str_arg(1, value),
            TaskerArg.int_arg(2, 0),
            TaskerArg.int_arg(3, 0),
        ],
    )


def if_condition(lhs: str, rhs: str, op: int = OP_EQUALS) -> TaskerAction:
    """Build an If (code 37) action with a single condition."""
    return TaskerAction(
        code=CODE_IF,
        conditions=[TaskerCondition(lhs=lhs, op=op, rhs=rhs)],
    )


def end_if() -> TaskerAction:
    """Build an End If (code 38) action."""
    return TaskerAction(code=CODE_END_IF)


def else_action() -> TaskerAction:
    """Build an Else (code 43) action."""
    return TaskerAction(code=CODE_ELSE)


def wait(seconds: int = 0, minutes: int = 0) -> TaskerAction:
    """Build a Wait (code 30) action."""
    return TaskerAction(
        code=CODE_WAIT,
        args=[
            TaskerArg.int_arg(0, 0),  # ms
            TaskerArg.int_arg(1, seconds),
            TaskerArg.int_arg(2, minutes),
            TaskerArg.int_arg(3, 0),  # hours
            TaskerArg.int_arg(4, 0),
        ],
    )


def stop() -> TaskerAction:
    """Build a Stop (code 137) action."""
    return TaskerAction(code=CODE_STOP)


def variable_search_replace(
    var_name: str,
    search: str,
    result_var: str = "",
) -> TaskerAction:
    """Build a Variable Search Replace (code 598) action."""
    return TaskerAction(
        code=CODE_VARIABLE_SEARCH_REPLACE,
        args=[
            TaskerArg.str_arg(0, var_name),
            TaskerArg.str_arg(1, search),
            TaskerArg.str_arg(2, result_var),
            TaskerArg.int_arg(3, 0),
            TaskerArg.int_arg(4, 0),
        ],
    )


def http_request(
    method: str = "GET",
    url: str = "",
    headers: str = "",
    body: str = "",
    timeout: int = 10,
    follow_redirects: bool = True,
) -> TaskerAction:
    """Build an HTTP Request (code 339) action.

    Args:
        method: "GET" or "POST".
        url: Request URL (Tasker variables expanded at runtime).
        headers: Newline-separated "Key:Value" header lines.
        body: POST body (URL-encoded).
        timeout: Timeout in seconds.
        follow_redirects: Whether to follow HTTP redirects.
    """
    method_code = 1 if method.upper() == "POST" else 0
    redirects_code = 0 if follow_redirects else 1
    return TaskerAction(
        code=CODE_HTTP_REQUEST,
        args=[
            TaskerArg.bundle_arg(0, _HTTP_BUNDLE_XML),
            TaskerArg.int_arg(1, method_code),
            TaskerArg.str_arg(2, url),
            TaskerArg.str_arg(3, headers),
            TaskerArg.str_arg(4, body),
            TaskerArg.str_arg(5),
            TaskerArg.str_arg(6),
            TaskerArg.str_arg(7),
            TaskerArg.int_arg(8, timeout),
            TaskerArg.int_arg(9, redirects_code),
            TaskerArg.int_arg(10, 0),
            TaskerArg.int_arg(11, 0),
            TaskerArg.int_arg(12, 1),
        ],
    )


def connect_wifi(ssid: str) -> TaskerAction:
    """Build a Connect to WiFi (code 398) action."""
    return TaskerAction(
        code=CODE_CONNECT_WIFI,
        args=[
            TaskerArg.str_arg(0, ssid),
            TaskerArg.int_arg(1, 0),
            TaskerArg.str_arg(2),
            TaskerArg.int_arg(3, 0),
            TaskerArg.int_arg(4, 0),
        ],
    )


def run_shell(
    command: str,
    timeout: int = 10,
    use_root: bool = False,
    output_var: str = "",
) -> TaskerAction:
    """Build a Run Shell (code 123) action.

    Note: arg1=timeout, arg2=use_root, arg3=output_var (Tasker 6.x order).
    """
    return TaskerAction(
        code=CODE_RUN_SHELL,
        args=[
            TaskerArg.str_arg(0, command),
            TaskerArg.int_arg(1, timeout),
            TaskerArg.int_arg(2, 1 if use_root else 0),
            TaskerArg.str_arg(3, output_var),
            TaskerArg.str_arg(4),
            TaskerArg.str_arg(5),
            TaskerArg.int_arg(6, 1),
            TaskerArg.int_arg(7, 0),
            TaskerArg.int_arg(8, 0),
        ],
    )


def goto_action(action_number: int) -> TaskerAction:
    """Build a Goto (code 731) action to jump to a specific action number.

    Args:
        action_number: The 1-based action number to jump to.
    """
    return TaskerAction(
        code=CODE_GOTO,
        args=[
            TaskerArg.str_arg(0, "Action Number"),
            TaskerArg.int_arg(1, action_number),
        ],
    )


def termux_task(
    executable: str,
    arguments: str = "",
    background: bool = True,
) -> TaskerAction:
    """Build a Termux:Tasker plugin action.

    This uses the Termux:Tasker plugin to execute a script in Termux's
    full environment.  The plugin action format is based on the official
    Termux:Tasker template export.

    Args:
        executable: Script name in ~/.termux/tasker/ (no path needed).
        arguments: Arguments to pass to the script (space-separated).
        background: Run in background (no terminal window).
    """
    # Build the Bundle XML matching the official Termux:Tasker template.
    # The Bundle contains plugin-specific extras that Tasker passes to
    # Termux:Tasker's FireReceiver.
    blurb = f"{executable} {arguments}".strip()
    bundle_xml = (
        '<Vals sr="val">'
        f"<com.termux.execute.arguments>{arguments}</com.termux.execute.arguments>"
        "<com.termux.execute.arguments-type>java.lang.String"
        "</com.termux.execute.arguments-type>"
        f"<com.termux.tasker.extra.EXECUTABLE>{executable}"
        "</com.termux.tasker.extra.EXECUTABLE>"
        "<com.termux.tasker.extra.EXECUTABLE-type>java.lang.String"
        "</com.termux.tasker.extra.EXECUTABLE-type>"
        f"<com.termux.tasker.extra.TERMINAL>"
        f"{'false' if background else 'true'}"
        "</com.termux.tasker.extra.TERMINAL>"
        "<com.termux.tasker.extra.TERMINAL-type>java.lang.Boolean"
        "</com.termux.tasker.extra.TERMINAL-type>"
        "<com.termux.tasker.extra.VERSION_CODE>4"
        "</com.termux.tasker.extra.VERSION_CODE>"
        "<com.termux.tasker.extra.VERSION_CODE-type>java.lang.Integer"
        "</com.termux.tasker.extra.VERSION_CODE-type>"
        "<com.termux.tasker.extra.WORKDIR></com.termux.tasker.extra.WORKDIR>"
        "<com.termux.tasker.extra.WORKDIR-type>java.lang.String"
        "</com.termux.tasker.extra.WORKDIR-type>"
        f"<com.twofortyfouram.locale.intent.extra.BLURB>{blurb}"
        "</com.twofortyfouram.locale.intent.extra.BLURB>"
        "<com.twofortyfouram.locale.intent.extra.BLURB-type>java.lang.String"
        "</com.twofortyfouram.locale.intent.extra.BLURB-type>"
        "<net.dinglisch.android.tasker.subbundled>true"
        "</net.dinglisch.android.tasker.subbundled>"
        "<net.dinglisch.android.tasker.subbundled-type>java.lang.Boolean"
        "</net.dinglisch.android.tasker.subbundled-type>"
        "</Vals>"
    )
    return TaskerAction(
        code=CODE_TERMUX_TASK,
        args=[
            TaskerArg.bundle_arg(0, bundle_xml),
            # arg1: plugin package name
            TaskerArg.str_arg(1, "com.termux.tasker"),
            # arg2: plugin config activity
            TaskerArg.str_arg(2, "com.termux.tasker.EditConfigurationActivity"),
            # arg3: plugin version code
            TaskerArg.int_arg(3, 10),
        ],
    )


# ---------------------------------------------------------------------------
# MVwifiAuto project builder
# ---------------------------------------------------------------------------
def _build_debug_flash_task() -> TaskerTask:
    """Build the DebugFlash helper task (id=10)."""
    return TaskerTask(
        id=10,
        name="DebugFlash",
        priority=2,
        actions=[
            TaskerAction(
                code=CODE_IF,
                conditions=[TaskerCondition(lhs="%DebugMode", op=OP_EQUALS, rhs="true")],
            ),
            flash("%par1"),
            end_if(),
        ],
    )


def _build_debug_on_task() -> TaskerTask:
    """Build the DebugOn task (id=20)."""
    return TaskerTask(
        id=20,
        name="DebugOn",
        actions=[
            variable_set("%DebugMode", "true"),
            flash("Debug logging ON"),
        ],
    )


def _build_debug_off_task() -> TaskerTask:
    """Build the DebugOff task (id=30)."""
    return TaskerTask(
        id=30,
        name="DebugOff",
        actions=[
            variable_set("%DebugMode", "false"),
            flash("Debug logging OFF"),
        ],
    )


def _build_handle_portal_task() -> TaskerTask:
    """Build the HandlePortal task (id=40).

    Uses dynamic portal host detection via redirect URL, matching the
    approach validated in Android devlog Session 17.
    """
    return TaskerTask(
        id=40,
        name="HandlePortal",
        actions=[
            # A1: Debug entry
            debug_flash("[HandlePortal] v19 starting"),
            # A1b: Test curl availability
            TaskerAction(
                code=CODE_RUN_SHELL,
                continue_on_error=True,
                args=[
                    TaskerArg.str_arg(0, "/data/local/tmp/curl --version"),
                    TaskerArg.int_arg(1, 10),
                    TaskerArg.int_arg(2, 0),
                    TaskerArg.str_arg(3, "%CurlTest"),
                    TaskerArg.str_arg(4),
                    TaskerArg.str_arg(5),
                    TaskerArg.int_arg(6, 1),
                    TaskerArg.int_arg(7, 0),
                    TaskerArg.int_arg(8, 0),
                ],
            ),
            # A1c: Flash curl test result
            debug_flash("curl: %CurlTest"),
            # A2: Wait 3s for WiFi to settle
            wait(seconds=3),
            # A4: HTTP GET 1.1.1.1 — follow redirect to get portal URL
            TaskerAction(
                code=CODE_HTTP_REQUEST,
                continue_on_error=True,
                args=[
                    TaskerArg.bundle_arg(0, _HTTP_BUNDLE_XML),
                    TaskerArg.int_arg(1, 0),
                    TaskerArg.int_arg(10, 0),
                    TaskerArg.int_arg(11, 0),
                    TaskerArg.int_arg(12, 1),
                    TaskerArg.str_arg(
                        2,
                        "http://1.1.1.1/",
                    ),
                    TaskerArg.str_arg(
                        3,
                        "User-Agent:Mozilla/5.0 (Linux; Android 10) "
                        "AppleWebKit/537.36 Chrome/120 Safari/537.36",
                    ),
                    TaskerArg.str_arg(4),
                    TaskerArg.str_arg(5),
                    TaskerArg.str_arg(6),
                    TaskerArg.str_arg(7),
                    TaskerArg.int_arg(8, 10),
                    TaskerArg.int_arg(9, 0),
                ],
            ),
            # A5: Extract portal host:port from redirect URL
            variable_search_replace(
                "%http_response_url",
                "http://([^/]+)/.*",
                "%PortalHost",
            ),
            # A5b: Debug portal host
            debug_flash("Portal: %PortalHost"),
            # A6: HTTP POST to portal acceptance endpoint
            TaskerAction(
                code=CODE_HTTP_REQUEST,
                continue_on_error=True,
                args=[
                    TaskerArg.bundle_arg(0, _HTTP_BUNDLE_XML),
                    TaskerArg.int_arg(1, 1),
                    TaskerArg.int_arg(10, 0),
                    TaskerArg.int_arg(11, 0),
                    TaskerArg.int_arg(12, 1),
                    TaskerArg.str_arg(2, "http://%PortalHost/forms/guest_toued"),
                    TaskerArg.str_arg(
                        3,
                        "Content-Type:application/x-www-form-urlencoded\n"
                        "User-Agent:Mozilla/5.0 (Linux; Android 10) "
                        "AppleWebKit/537.36 Chrome/120 Safari/537.36\n"
                        "Referer:http://%PortalHost/",
                    ),
                    TaskerArg.str_arg(
                        4,
                        "origurl=http%3a%2f%2f1%2e1%2e1%2e1%2f&ok=Accept+and+Continue",
                    ),
                    TaskerArg.str_arg(5),
                    TaskerArg.str_arg(6),
                    TaskerArg.str_arg(7),
                    TaskerArg.int_arg(8, 10),
                    TaskerArg.int_arg(9, 0),
                ],
            ),
            # A7: Debug POST response code
            debug_flash("POST: %http_response_code"),
            # A8: Verify internet via WiFi
            TaskerAction(
                code=CODE_HTTP_REQUEST,
                args=[
                    TaskerArg.bundle_arg(0, _HTTP_BUNDLE_XML),
                    TaskerArg.int_arg(1, 0),
                    TaskerArg.int_arg(10, 0),
                    TaskerArg.int_arg(11, 0),
                    TaskerArg.int_arg(12, 1),
                    TaskerArg.str_arg(2, "http://detectportal.firefox.com/success.txt"),
                    TaskerArg.str_arg(3),
                    TaskerArg.str_arg(4),
                    TaskerArg.str_arg(5),
                    TaskerArg.str_arg(6),
                    TaskerArg.str_arg(7),
                    TaskerArg.int_arg(8, 10),
                    TaskerArg.int_arg(9, 0),
                ],
            ),
            # A9: Store verify result
            variable_set("%VerifyResult", "%http_response_code"),
            # A10: If 200 — success
            if_condition("%VerifyResult", "200"),
            debug_flash("[HandlePortal] Success: Connected with internet!"),
            else_action(),
            debug_flash("[HandlePortal] Failed: Portal acceptance failed"),
            end_if(),
        ],
    )


def _build_connect_to_cmvwifi_task() -> TaskerTask:
    """Build the ConnectToCmvwifi task (id=50)."""
    return TaskerTask(
        id=50,
        name="ConnectToCmvwifi",
        actions=[
            # A1: Debug entry
            debug_flash("[ConnectToCmvwifi] cmvwifi detected, checking connection..."),
            # A2: If already connected to cmvwifi
            if_condition("%WIFII", "cmvwifi"),
            # A3: Already connected, go straight to portal
            debug_flash("[ConnectToCmvwifi] Already connected, handling portal..."),
            # A4: Call HandlePortal
            perform_task("HandlePortal", wait_for_finish=True),
            # A5: Else - not connected
            else_action(),
            # A6: Connect to cmvwifi
            connect_wifi("cmvwifi"),
            # A7: Debug connection status
            debug_flash("[ConnectToCmvwifi] Connected, waiting for portal..."),
            # A8: Wait 5 seconds
            wait(seconds=5),
            # A9: Call HandlePortal
            perform_task("HandlePortal", wait_for_finish=True),
            # A10: End If
            end_if(),
        ],
    )


def _build_test_wifi_scan_task() -> TaskerTask:
    """Build the TestWiFiScan task (id=60)."""
    return TaskerTask(
        id=60,
        name="TestWiFiScan",
        actions=[
            debug_flash("[TestWiFiScan] Starting WiFi scan test"),
            variable_set("%CurrentSSID", "%WIFII"),
            debug_flash("[TestWiFiScan] Current network: %CurrentSSID"),
            if_condition("%CurrentSSID", "*dd-wrt*"),
            debug_flash("[TestWiFiScan] Home network dd-wrt detected!"),
            stop(),
            end_if(),
            debug_flash("[TestWiFiScan] Not on dd-wrt. Current: %CurrentSSID"),
        ],
    )


def _build_cmvwifi_profile() -> TaskerProfile:
    """Build the cmvwifi Auto Connect profile (id=1)."""
    return TaskerProfile(
        id=1,
        name="cmvwifi Auto Connect",
        state=TaskerState(
            code=CODE_WIFI_NEAR_STATE,
            args=[
                TaskerArg.str_arg(0, "cmvwifi"),   # SSID
                TaskerArg.str_arg(1),              # MAC (empty = any)
                TaskerArg.str_arg(2),              # Capabilities (empty = any)
                TaskerArg.int_arg(3, 0),           # Min Activate Signal Level
                TaskerArg.int_arg(4, 0),           # Channel (0 = any)
                TaskerArg.int_arg(5, 0),           # Toggle WiFi (0 = off)
            ],
        ),
        task_id=50,
    )


def build_mvwifi_project() -> TaskerProject:
    """Build the complete MVwifiAuto Tasker project (pure-Tasker approach).

    This is the original pure-Tasker approach using HTTP Request actions
    for portal handling.  It does NOT work on Android 16 due to policy
    routing (see android-devlog.md Sessions 14-17).  Kept for reference
    and for devices where the policy routing issue doesn't apply.

    Returns:
        A :class:`TaskerProject` containing all tasks and the WiFi Near
        profile, ready for XML generation.
    """
    tasks = [
        _build_debug_flash_task(),
        _build_debug_on_task(),
        _build_debug_off_task(),
        _build_handle_portal_task(),
        _build_connect_to_cmvwifi_task(),
        _build_test_wifi_scan_task(),
    ]
    profiles = [_build_cmvwifi_profile()]
    return TaskerProject(
        name="MVwifiAuto",
        profiles=profiles,
        tasks=tasks,
    )


# ---------------------------------------------------------------------------
# Termux project builder (recommended approach)
# ---------------------------------------------------------------------------
def _build_run_portal_script_task_termux() -> TaskerTask:
    """Build the RunPortalScript task (id=70) — Termux:Tasker plugin.

    This task runs the Python portal handler via the Termux:Tasker plugin.
    The plugin executes the wrapper script at ~/.termux/tasker/mvwifi_portal
    in Termux's full environment.
    """
    return TaskerTask(
        id=70,
        name="RunPortalScript",
        actions=[
            # A1: Run the portal handler via Termux:Tasker plugin
            termux_task("mvwifi_portal", background=True),
        ],
    )


def _build_connect_and_run_task_termux() -> TaskerTask:
    """Build the ConnectAndRun task (id=80) — Termux approach.

    Connects to cmvwifi (if not already connected), waits for DHCP,
    then calls RunPortalScript to handle the captive portal.
    """
    return TaskerTask(
        id=80,
        name="ConnectAndRun",
        actions=[
            # A1: Store current SSID
            variable_set("%CurrentSSID", "%WIFII"),
            # A2: If already on cmvwifi, skip connection
            if_condition("%CurrentSSID", "cmvwifi"),
            # A3: Goto A6 (Perform Task) — skip connect and wait
            goto_action(6),
            # A4: End If
            end_if(),
            # A5: Connect to cmvwifi
            connect_wifi("cmvwifi"),
            # A6: Wait 5 seconds for DHCP
            wait(seconds=5),
            # A7: Run the portal script
            perform_task("RunPortalScript", wait_for_finish=True),
            # A8: Flash completion
            flash("Portal handling complete"),
        ],
    )


def _build_cmvwifi_profile_termux() -> TaskerProfile:
    """Build the cmvwifi Auto Connect profile (id=2) — Termux approach."""
    return TaskerProfile(
        id=2,
        name="cmvwifi Auto Connect",
        state=TaskerState(
            code=CODE_WIFI_NEAR_STATE,
            args=[
                TaskerArg.str_arg(0, "cmvwifi"),   # SSID
                TaskerArg.str_arg(1),              # MAC (empty = any)
                TaskerArg.str_arg(2),              # Capabilities (empty = any)
                TaskerArg.int_arg(3, 0),           # Min Activate Signal Level
                TaskerArg.int_arg(4, 0),           # Channel (0 = any)
                TaskerArg.int_arg(5, 0),           # Toggle WiFi (0 = off)
            ],
        ),
        task_id=80,  # ConnectAndRun
    )


def build_termux_project() -> TaskerProject:
    """Build the MVwifiAuto Tasker project for the Termux approach.

    This is the recommended approach.  Tasker handles WiFi detection
    and connection; the Python script (via Termux:Tasker plugin) handles
    the captive portal with SO_BINDTODEVICE interface binding.

    Tasks:
        - DebugFlash: shared debug helper (reused from pure-Tasker version)
        - DebugOn / DebugOff: toggle debug mode
        - RunPortalScript: runs mvwifi-android via Termux:Tasker plugin
        - ConnectAndRun: connects to cmvwifi, waits for DHCP, calls
          RunPortalScript

    Profile:
        - cmvwifi Auto Connect: WiFi Near → ConnectAndRun

    Returns:
        A :class:`TaskerProject` ready for XML generation.
    """
    tasks = [
        _build_debug_flash_task(),
        _build_debug_on_task(),
        _build_debug_off_task(),
        _build_run_portal_script_task_termux(),
        _build_connect_and_run_task_termux(),
    ]
    profiles = [_build_cmvwifi_profile_termux()]
    return TaskerProject(
        name="MVwifiAuto-Termux",
        profiles=profiles,
        tasks=tasks,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    """CLI entry point for generating the Tasker XML.

    Args:
        argv: Command-line arguments (default: ``sys.argv[1:]``).

    Returns:
        0 on success.
    """
    parser = argparse.ArgumentParser(
        description="Generate the MVwifiAuto Tasker .prj.xml file",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="android/MVwifiAuto.prj.xml",
        help="Output file path (default: android/MVwifiAuto.prj.xml)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print XML to stdout instead of writing a file",
    )
    parser.add_argument(
        "--termux",
        action="store_true",
        help="Generate the Termux approach project (recommended) instead of "
        "the pure-Tasker approach",
    )

    args = parser.parse_args(argv)

    if args.termux:
        project = build_termux_project()
        if args.output == "android/MVwifiAuto.prj.xml":
            args.output = "android/MVwifiAuto-Termux.prj.xml"
    else:
        project = build_mvwifi_project()

    xml_text = generate_project_xml(project)

    if args.stdout:
        print(xml_text)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(xml_text)
        print(f"Written {len(xml_text)} bytes to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
