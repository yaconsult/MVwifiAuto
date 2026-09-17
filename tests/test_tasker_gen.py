"""Tests for the Tasker XML generator."""

from xml.dom.minidom import parseString
from xml.etree.ElementTree import fromstring

from mvwifi_auto.tasker_gen import (
    CODE_CONNECT_WIFI,
    CODE_ELSE,
    CODE_END_IF,
    CODE_FLASH,
    CODE_GOTO,
    CODE_HTTP_REQUEST,
    CODE_IF,
    CODE_PERFORM_TASK,
    CODE_RUN_SHELL,
    CODE_STOP,
    CODE_TERMUX_TASK,
    CODE_VARIABLE_SEARCH_REPLACE,
    CODE_VARIABLE_SET,
    CODE_WAIT,
    CODE_WIFI_NEAR_STATE,
    OP_EQUALS,
    TaskerArg,
    TaskerProject,
    TaskerTask,
    build_mvwifi_project,
    build_termux_project,
    connect_wifi,
    debug_flash,
    else_action,
    end_if,
    flash,
    generate_project_xml,
    goto_action,
    http_request,
    if_condition,
    perform_task,
    run_shell,
    stop,
    termux_task,
    variable_search_replace,
    variable_set,
    wait,
)


class TestArgBuilders:
    """Test argument builder helpers."""

    def test_str_arg(self):
        arg = TaskerArg.str_arg(0, "hello")
        assert arg.index == 0
        assert arg.kind == "Str"
        assert arg.value == "hello"

    def test_int_arg(self):
        arg = TaskerArg.int_arg(1, 42)
        assert arg.index == 1
        assert arg.kind == "Int"
        assert arg.value == "42"

    def test_bundle_arg(self):
        arg = TaskerArg.bundle_arg(0, "<Vals/>")
        assert arg.index == 0
        assert arg.kind == "Bundle"
        assert arg.value == "<Vals/>"


class TestActionBuilders:
    """Test action builder helpers."""

    def test_perform_task(self):
        action = perform_task("DebugFlash", par1="hello")
        assert action.code == CODE_PERFORM_TASK
        assert action.args[0].value == "DebugFlash"
        assert action.args[2].value == "hello"
        assert action.args[10].value == "1"  # wait_for_finish

    def test_flash(self):
        action = flash("test message")
        assert action.code == CODE_FLASH
        assert action.args[0].value == "test message"

    def test_debug_flash(self):
        action = debug_flash("my message")
        assert action.code == CODE_PERFORM_TASK
        assert action.args[0].value == "DebugFlash"
        assert action.args[2].value == "my message"

    def test_variable_set(self):
        action = variable_set("%Foo", "bar")
        assert action.code == CODE_VARIABLE_SET
        assert action.args[0].value == "%Foo"
        assert action.args[1].value == "bar"

    def test_if_condition(self):
        action = if_condition("%WIFII", "cmvwifi")
        assert action.code == CODE_IF
        assert action.conditions is not None
        assert action.conditions[0].lhs == "%WIFII"
        assert action.conditions[0].op == OP_EQUALS
        assert action.conditions[0].rhs == "cmvwifi"

    def test_end_if(self):
        action = end_if()
        assert action.code == CODE_END_IF
        assert action.args == []

    def test_else_action(self):
        action = else_action()
        assert action.code == CODE_ELSE

    def test_wait(self):
        action = wait(seconds=5)
        assert action.code == CODE_WAIT
        assert action.args[1].value == "5"  # seconds

    def test_wait_minutes(self):
        action = wait(minutes=3)
        assert action.code == CODE_WAIT
        assert action.args[2].value == "3"  # minutes

    def test_stop(self):
        action = stop()
        assert action.code == CODE_STOP

    def test_variable_search_replace(self):
        action = variable_search_replace("%URL", "http://([^/]+)/.*", "%Host")
        assert action.code == CODE_VARIABLE_SEARCH_REPLACE
        assert action.args[0].value == "%URL"
        assert action.args[1].value == "http://([^/]+)/.*"
        assert action.args[2].value == "%Host"

    def test_http_request_get(self):
        action = http_request(method="GET", url="http://1.1.1.1/")
        assert action.code == CODE_HTTP_REQUEST
        assert action.args[1].value == "0"  # method=GET
        assert action.args[2].value == "http://1.1.1.1/"

    def test_http_request_post(self):
        action = http_request(
            method="POST",
            url="http://10.64.2.21:9997/forms/guest_toued",
            headers="Content-Type:application/x-www-form-urlencoded",
            body="origurl=test&ok=Accept",
        )
        assert action.code == CODE_HTTP_REQUEST
        assert action.args[1].value == "1"  # method=POST
        assert action.args[3].value == "Content-Type:application/x-www-form-urlencoded"
        assert action.args[4].value == "origurl=test&ok=Accept"

    def test_http_request_no_redirects(self):
        action = http_request(follow_redirects=False)
        assert action.args[9].value == "1"  # redirects off

    def test_connect_wifi(self):
        action = connect_wifi("cmvwifi")
        assert action.code == CODE_CONNECT_WIFI
        assert action.args[0].value == "cmvwifi"

    def test_run_shell(self):
        action = run_shell("echo hello", timeout=5, output_var="%Result")
        assert action.code == CODE_RUN_SHELL
        assert action.args[0].value == "echo hello"
        assert action.args[1].value == "5"  # timeout
        assert action.args[2].value == "0"  # use_root=False
        assert action.args[3].value == "%Result"


class TestXmlGeneration:
    """Test XML generation from data structures."""

    def test_generates_valid_xml(self):
        """Test that the generated XML is well-formed."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        # Should parse without error
        root = fromstring(xml_text)
        assert root.tag == "TaskerData"

    def test_has_xml_declaration(self):
        """Test that the XML starts with a declaration."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        assert xml_text.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    def test_root_attributes(self):
        """Test that the root element has correct attributes."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        assert root.get("sr") == ""
        assert root.get("dvi") == "1"
        assert root.get("tv") == "5.15.14"

    def test_project_element(self):
        """Test that the Project element exists with correct name."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        proj = root.find("Project")
        assert proj is not None
        assert proj.find("name").text == "MVwifiAuto"

    def test_profile_element(self):
        """Test that the WiFi Near profile exists and links to task 50."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        profile = root.find("Profile")
        assert profile is not None
        assert profile.find("nme").text == "cmvwifi Auto Connect"
        assert profile.find("mid0").text == "50"
        state = profile.find("State")
        assert state is not None
        assert state.find("code").text == str(CODE_WIFI_NEAR_STATE)

    def test_wifi_near_state_args(self):
        """Test WiFi Near state has correct parameter order and types.

        WiFi Near state args must be:
          arg0: SSID (Str), arg1: MAC (Str), arg2: Capabilities (Str),
          arg3: Min Signal (Int), arg4: Channel (Int), arg5: Toggle WiFi (Int)
        """
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        state = root.find("Profile").find("State")
        assert state is not None
        args = state.findall("Str") + state.findall("Int")
        # Should have 6 args: 3 Str + 3 Int
        assert len(args) == 6
        # arg0: SSID = "cmvwifi" (Str)
        assert state.find('Str[@sr="arg0"]').text == "cmvwifi"
        # arg1: MAC = "" (Str, empty = any)
        assert state.find('Str[@sr="arg1"]').text in (None, "")
        # arg2: Capabilities = "" (Str, empty = any)
        assert state.find('Str[@sr="arg2"]').text in (None, "")
        # arg3: Min Signal = 0 (Int)
        assert state.find('Int[@sr="arg3"]').get("val") == "0"
        # arg4: Channel = 0 (Int)
        assert state.find('Int[@sr="arg4"]').get("val") == "0"
        # arg5: Toggle WiFi = 0 (Int)
        assert state.find('Int[@sr="arg5"]').get("val") == "0"

    def test_all_six_tasks_present(self):
        """Test that all six tasks are present in the XML."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        assert len(tasks) == 6
        task_names = {t.find("nme").text for t in tasks}
        assert task_names == {
            "DebugFlash",
            "DebugOn",
            "DebugOff",
            "HandlePortal",
            "ConnectToCmvwifi",
            "TestWiFiScan",
        }

    def test_task_ids(self):
        """Test that task IDs match expected values."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        task_ids = {int(t.find("id").text) for t in tasks}
        assert task_ids == {10, 20, 30, 40, 50, 60}

    def test_debug_flash_has_if_block(self):
        """Test that DebugFlash task has an If block with %DebugMode condition."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        debug_flash_task = next(t for t in tasks if t.find("nme").text == "DebugFlash")
        actions = debug_flash_task.findall("Action")
        # First action should be If
        assert actions[0].find("code").text == str(CODE_IF)
        cond_list = actions[0].find("ConditionList")
        assert cond_list is not None
        cond = cond_list.find("Condition")
        assert cond.find("lhs").text == "%DebugMode"
        assert cond.find("rhs").text == "true"

    def test_handle_portal_has_http_requests(self):
        """Test that HandlePortal has HTTP Request actions."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        handle_portal = next(t for t in tasks if t.find("nme").text == "HandlePortal")
        actions = handle_portal.findall("Action")
        http_actions = [a for a in actions if a.find("code").text == str(CODE_HTTP_REQUEST)]
        # Should have at least 3 HTTP requests: GET 1.1.1.1, POST portal, GET verify
        assert len(http_actions) >= 3

    def test_connect_to_cmvwifi_has_if_else(self):
        """Test that ConnectToCmvwifi has If/Else/End If structure."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        connect_task = next(t for t in tasks if t.find("nme").text == "ConnectToCmvwifi")
        actions = connect_task.findall("Action")
        codes = [int(a.find("code").text) for a in actions]
        assert CODE_IF in codes
        assert CODE_ELSE in codes
        assert CODE_END_IF in codes

    def test_continue_on_error_attribute(self):
        """Test that continue_on_error actions have <con>true</con>."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        # HandlePortal's curl test action has continue_on_error=True
        tasks = root.findall("Task")
        handle_portal = next(t for t in tasks if t.find("nme").text == "HandlePortal")
        actions = handle_portal.findall("Action")
        con_actions = [a for a in actions if a.find("con") is not None]
        assert len(con_actions) > 0
        assert con_actions[0].find("con").text == "true"

    def test_project_tids(self):
        """Test that the project tids field lists all task IDs."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        proj = root.find("Project")
        tids = proj.find("tids").text
        assert "10" in tids
        assert "20" in tids
        assert "40" in tids
        assert "50" in tids
        assert "60" in tids

    def test_custom_project(self):
        """Test generating XML for a custom minimal project."""
        task = TaskerTask(
            id=1,
            name="TestTask",
            actions=[flash("hello")],
        )
        project = TaskerProject(
            name="Test",
            profiles=[],
            tasks=[task],
        )
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        assert root.find("Project").find("name").text == "Test"
        assert root.find("Task").find("nme").text == "TestTask"

    def test_parses_with_xml_parser(self):
        """Test that the XML can be parsed by a strict XML parser."""
        project = build_mvwifi_project()
        xml_text = generate_project_xml(project)
        # parseString raises on malformed XML
        parseString(xml_text.encode("utf-8"))


class TestTermuxProject:
    """Test the Termux approach project builder."""

    def test_generates_valid_xml(self):
        """Test that the Termux project XML is well-formed."""
        project = build_termux_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        assert root.tag == "TaskerData"

    def test_parses_with_xml_parser(self):
        """Test that the Termux XML can be parsed by a strict parser."""
        project = build_termux_project()
        xml_text = generate_project_xml(project)
        parseString(xml_text.encode("utf-8"))

    def test_project_name(self):
        """Test that the project name is MVwifiAuto-Termux."""
        project = build_termux_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        assert root.find("Project").find("name").text == "MVwifiAuto-Termux"

    def test_has_five_tasks(self):
        """Test that the Termux project has 5 tasks."""
        project = build_termux_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        assert len(tasks) == 5
        task_names = {t.find("nme").text for t in tasks}
        assert task_names == {
            "DebugFlash",
            "DebugOn",
            "DebugOff",
            "RunPortalScript",
            "ConnectAndRun",
        }

    def test_profile_links_to_connect_and_run(self):
        """Test that the WiFi Near profile links to ConnectAndRun (id=80)."""
        project = build_termux_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        profile = root.find("Profile")
        assert profile is not None
        assert profile.find("nme").text == "cmvwifi Auto Connect"
        assert profile.find("mid0").text == "80"

    def test_run_portal_script_has_termux_plugin(self):
        """Test that RunPortalScript uses the Termux:Tasker plugin."""
        project = build_termux_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        run_script = next(t for t in tasks if t.find("nme").text == "RunPortalScript")
        actions = run_script.findall("Action")
        assert len(actions) == 1
        # The action should have code 1256900802 (Termux:Tasker plugin)
        assert actions[0].find("code").text == "1256900802"
        # The Bundle arg contains the plugin config as child elements
        bundles = actions[0].findall("Bundle")
        assert len(bundles) == 1
        # Serialize the bundle to check its content
        from xml.etree.ElementTree import tostring
        bundle_xml = tostring(bundles[0], encoding="unicode")
        assert "mvwifi_portal" in bundle_xml
        assert "com.termux.tasker.extra.EXECUTABLE" in bundle_xml

    def test_connect_and_run_has_wifi_connect(self):
        """Test that ConnectAndRun has a Connect to WiFi action."""
        project = build_termux_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        connect_task = next(t for t in tasks if t.find("nme").text == "ConnectAndRun")
        actions = connect_task.findall("Action")
        codes = [int(a.find("code").text) for a in actions]
        assert CODE_CONNECT_WIFI in codes

    def test_connect_and_run_has_wait(self):
        """Test that ConnectAndRun has a Wait action for DHCP."""
        project = build_termux_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        connect_task = next(t for t in tasks if t.find("nme").text == "ConnectAndRun")
        actions = connect_task.findall("Action")
        codes = [int(a.find("code").text) for a in actions]
        assert CODE_WAIT in codes

    def test_connect_and_run_has_perform_task(self):
        """Test that ConnectAndRun calls RunPortalScript via Perform Task."""
        project = build_termux_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        connect_task = next(t for t in tasks if t.find("nme").text == "ConnectAndRun")
        actions = connect_task.findall("Action")
        perform_actions = [a for a in actions if a.find("code").text == str(CODE_PERFORM_TASK)]
        assert len(perform_actions) >= 1
        # The first arg should be the task name "RunPortalScript"
        str_args = perform_actions[0].findall("Str")
        assert any(s.text == "RunPortalScript" for s in str_args)

    def test_connect_and_run_has_if_goto(self):
        """Test that ConnectAndRun has If + Goto for already-connected check."""
        project = build_termux_project()
        xml_text = generate_project_xml(project)
        root = fromstring(xml_text)
        tasks = root.findall("Task")
        connect_task = next(t for t in tasks if t.find("nme").text == "ConnectAndRun")
        actions = connect_task.findall("Action")
        codes = [int(a.find("code").text) for a in actions]
        assert CODE_IF in codes
        assert CODE_GOTO in codes
        assert CODE_END_IF in codes

    def test_termux_task_builder(self):
        """Test the termux_task action builder."""
        action = termux_task("mvwifi_portal", background=True)
        assert action.code == CODE_TERMUX_TASK
        # arg0: Bundle with plugin config
        assert action.args[0].kind == "Bundle"
        assert "mvwifi_portal" in action.args[0].value
        assert "com.termux.tasker.extra.EXECUTABLE" in action.args[0].value
        assert "false" in action.args[0].value  # background=true -> TERMINAL=false
        # arg1: plugin package
        assert action.args[1].value == "com.termux.tasker"
        # arg2: config activity
        assert action.args[2].value == "com.termux.tasker.EditConfigurationActivity"
        # arg3: version code
        assert action.args[3].value == "10"

    def test_goto_builder(self):
        """Test the goto_action builder."""
        action = goto_action(6)
        assert action.code == CODE_GOTO
        assert action.args[0].value == "Action Number"
        assert action.args[1].value == "6"
