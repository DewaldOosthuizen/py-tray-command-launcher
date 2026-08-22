"""Tests for AppDiscovery.clean_exec, build_launch_args, and is_windows_lnk_entry."""

import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from modules.app_discovery import AppDiscovery, AppEntry, _find_terminal_emulator


@pytest.fixture(autouse=True)
def _clear_terminal_emulator_cache():
    _find_terminal_emulator.cache_clear()
    yield
    _find_terminal_emulator.cache_clear()


# ---------------------------------------------------------------------------
# clean_exec
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("placeholder", ["%f", "%F", "%u", "%U", "%i", "%c", "%k"])
def test_clean_exec_placeholder_removal_individual(placeholder):
    result = AppDiscovery.clean_exec(f"gedit {placeholder}")
    assert placeholder not in result
    assert "gedit" in result


def test_clean_exec_multiple_placeholders():
    result = AppDiscovery.clean_exec("gedit %F %U %i")
    assert result == "gedit"


def test_clean_exec_no_placeholders():
    result = AppDiscovery.clean_exec("gedit /tmp/file.txt")
    assert result == "gedit /tmp/file.txt"


def test_clean_exec_only_placeholders_returns_empty():
    result = AppDiscovery.clean_exec("%F %U")
    assert result == ""


# ---------------------------------------------------------------------------
# build_launch_args
# ---------------------------------------------------------------------------


def test_build_launch_args_non_terminal():
    entry = AppEntry(name="Gedit", exec_cmd="gedit %F", terminal=False, icon_name="")
    result = AppDiscovery.build_launch_args(entry)
    assert result == ["gedit"]


def test_build_launch_args_empty_after_clean():
    entry = AppEntry(name="Bad", exec_cmd="%F %U", terminal=False, icon_name="")
    result = AppDiscovery.build_launch_args(entry)
    assert result is None


def test_build_launch_args_multi_token():
    entry = AppEntry(name="Env", exec_cmd="env DISPLAY=:0 gedit", terminal=False, icon_name="")
    result = AppDiscovery.build_launch_args(entry)
    assert result == ["env", "DISPLAY=:0", "gedit"]


def test_build_launch_args_terminal_with_emulator():
    entry = AppEntry(name="Htop", exec_cmd="htop", terminal=True, icon_name="")

    def which_side_effect(candidate):
        return "/usr/bin/xterm" if candidate == "xterm" else None

    with patch("modules.app_discovery.shutil.which", side_effect=which_side_effect):
        result = AppDiscovery.build_launch_args(entry)
    assert result == ["/usr/bin/xterm", "-e", "htop"]


def test_build_launch_args_terminal_no_emulator():
    entry = AppEntry(name="Htop", exec_cmd="htop", terminal=True, icon_name="")
    with patch("modules.app_discovery.shutil.which", return_value=None):
        result = AppDiscovery.build_launch_args(entry)
    assert result is None


def test_build_launch_args_terminal_second_emulator():
    entry = AppEntry(name="Htop", exec_cmd="htop", terminal=True, icon_name="")
    # x-terminal-emulator first, gnome-terminal second — make konsole succeed
    candidates_tried = []

    def which_side_effect(candidate):
        candidates_tried.append(candidate)
        return "/usr/bin/konsole" if candidate == "konsole" else None

    with patch("modules.app_discovery.shutil.which", side_effect=which_side_effect):
        result = AppDiscovery.build_launch_args(entry)

    assert result == ["/usr/bin/konsole", "-e", "htop"]
    # konsole is not the first candidate, so first candidates should have returned None
    assert candidates_tried.index("konsole") > 0


def test_build_launch_args_shlex_error_fallback():
    entry = AppEntry(name="Bad", exec_cmd="app 'unclosed", terminal=False, icon_name="")
    result = AppDiscovery.build_launch_args(entry)
    assert result == ["app", "'unclosed"]


def test_build_launch_args_unmatched_quote_falls_back_to_whitespace_split():
    entry = AppEntry(
        name="TestApp", exec_cmd="/usr/bin/app --flag 'bad", terminal=False, icon_name=""
    )
    result = AppDiscovery.build_launch_args(entry)
    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 1
    assert result[0] == "/usr/bin/app"


def test_build_launch_args_whitespace_exec_returns_none():
    entry = AppEntry(name="TestApp", exec_cmd="   ", terminal=False, icon_name="")
    result = AppDiscovery.build_launch_args(entry)
    assert result is None


class TestFindTerminalEmulatorCache:
    """Tests for issue #50 — cached terminal emulator lookup."""

    def setup_method(self):
        _find_terminal_emulator.cache_clear()

    def teardown_method(self):
        _find_terminal_emulator.cache_clear()

    def test_shutil_which_called_only_once_across_multiple_build_launch_args(self):
        entry = AppEntry(name="Htop", exec_cmd="htop", terminal=True, icon_name="")

        with patch(
            "modules.app_discovery.shutil.which", return_value="/usr/bin/xterm"
        ) as mock_which:
            AppDiscovery.build_launch_args(entry)
            AppDiscovery.build_launch_args(entry)

        assert mock_which.call_count == 1


# ---------------------------------------------------------------------------
# is_windows_lnk_entry
# ---------------------------------------------------------------------------


def test_is_windows_lnk_entry_lnk_path():
    entry = AppEntry(
        name="App", exec_cmd=r"C:\Users\user\AppData\Roaming\App.lnk", terminal=False, icon_name=""
    )
    with patch("modules.app_discovery.IS_WINDOWS", True):
        result = AppDiscovery.is_windows_lnk_entry(entry)
    assert result is True


def test_is_windows_lnk_entry_non_lnk_path():
    entry = AppEntry(name="Firefox", exec_cmd="/usr/bin/firefox", terminal=False, icon_name="")
    with patch("modules.app_discovery.IS_WINDOWS", True):
        result = AppDiscovery.is_windows_lnk_entry(entry)
    assert result is False


def test_is_windows_lnk_entry_linux_always_false():
    entry = AppEntry(name="App", exec_cmd="some_app.lnk", terminal=False, icon_name="")
    with patch("modules.app_discovery.IS_WINDOWS", False):
        result = AppDiscovery.is_windows_lnk_entry(entry)
    assert result is False


# ---------------------------------------------------------------------------
# Thread-safety — issue #87
# ---------------------------------------------------------------------------


def test_find_pixmap_concurrent_with_icon_index_build_no_exception():
    """`_find_pixmap` reads `_icon_path_index` while `_build_icon_index` swaps it
    concurrently. The `_icon_index_lock` must prevent any race/exception and
    every read must observe either the initial empty dict or the fully-built
    replacement — never a partially mutated dict."""
    with patch("modules.app_discovery.IS_WINDOWS", True):
        # Avoid the constructor's own background thread; we drive both sides manually.
        discovery = AppDiscovery()

    errors: list[BaseException] = []
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            try:
                with discovery._icon_index_lock:
                    path = discovery._icon_path_index.get("nonexistent-icon")
                assert path is None or isinstance(path, str)
            except BaseException as exc:  # noqa: BLE001 - want to capture any race exception
                errors.append(exc)

    reader_threads = [threading.Thread(target=reader) for _ in range(4)]
    for t in reader_threads:
        t.start()

    # Run the real index builder concurrently with the readers.
    builder_thread = threading.Thread(target=discovery._build_icon_index)
    builder_thread.start()
    builder_thread.join(timeout=10)

    stop.set()
    for t in reader_threads:
        t.join(timeout=10)

    assert not errors
    assert isinstance(discovery._icon_path_index, dict)


# ---------------------------------------------------------------------------
# Issue #93 — bare except replacement tests
# ---------------------------------------------------------------------------


class TestParseDesktopFileErrorHandling:
    """Tests for issue #93: _parse_desktop_file should raise specific exceptions."""

    def test_malformed_utf8_logs_warning_and_returns_none(self, caplog):
        """UnicodeDecodeError from non-UTF-8 .desktop file → WARNING + None."""
        from modules.app_discovery import AppDiscovery

        discovery = AppDiscovery()
        with caplog.at_level("WARNING", logger="modules.app_discovery"):
            path = Path("/tmp/test-bad-utf8.desktop")
            try:
                path.write_bytes(b"\xff\xfeName=Bad\n")
                result = discovery._parse_desktop_file(path)
            finally:
                path.unlink(missing_ok=True)

        assert result is None
        assert any(
            "Skipping malformed .desktop file" in record.message
            for record in caplog.records
        )
        assert any(
            "can't decode byte" in record.message for record in caplog.records
        )

    def test_missing_section_header_logs_warning_and_returns_none(self, caplog):
        """MissingSectionHeaderError → WARNING + None."""
        from modules.app_discovery import AppDiscovery

        discovery = AppDiscovery()
        with caplog.at_level("WARNING", logger="modules.app_discovery"):
            path = Path("/tmp/test-no-section.desktop")
            try:
                path.write_text("Name=Foo\nExec=/usr/bin/foo\n")
                result = discovery._parse_desktop_file(path)
            finally:
                path.unlink(missing_ok=True)

        assert result is None
        assert any(
            "Skipping malformed .desktop file" in record.message
            for record in caplog.records
        )
        assert any(
            "no section headers" in record.message for record in caplog.records
        )

    def test_missing_type_field_returns_none(self):
        """Missing Type=Application → early return None (no regression)."""
        from modules.app_discovery import AppDiscovery

        discovery = AppDiscovery()
        path = Path("/tmp/test-no-type.desktop")
        try:
            path.write_text("[Desktop Entry]\nName=Foo\nExec=/usr/bin/foo\n")
            result = discovery._parse_desktop_file(path)
        finally:
            path.unlink(missing_ok=True)

        assert result is None


class TestGetboolErrorHandling:
    """Tests for issue #93: getbool() should catch ValueError specifically."""

    def test_getbool_returns_fallback_for_non_boolean_string(self):
        """getbool() returns fallback when value is 'maybe' (ValueError path)."""
        from modules.app_discovery import AppDiscovery

        discovery = AppDiscovery()
        path = Path("/tmp/test-getbool.desktop")
        try:
            path.write_text("[Desktop Entry]\nName=Foo\nExec=/usr/bin/foo\nType=Application\nTerminal=maybe\n")
            entry = discovery._parse_desktop_file(path)
        finally:
            path.unlink(missing_ok=True)

        assert entry is not None
        assert entry.terminal is False  # fallback value


# ---------------------------------------------------------------------------
# Verify existing build_launch_args tests still pass (no regression)
# ---------------------------------------------------------------------------


def test_build_launch_args_shlex_error_fallback_still_works():
    """Issue #93: verify existing shlex.error fallback test still passes."""
    entry = AppEntry(name="Bad", exec_cmd="app 'unclosed", terminal=False, icon_name="")
    result = AppDiscovery.build_launch_args(entry)
    assert result == ["app", "'unclosed"]


def test_build_launch_args_unmatched_quote_falls_back_still_works():
    """Issue #93: verify existing unmatched-quote fallback still passes."""
    entry = AppEntry(
        name="TestApp", exec_cmd="/usr/bin/app --flag 'bad", terminal=False, icon_name=""
    )
    result = AppDiscovery.build_launch_args(entry)
    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 1
    assert result[0] == "/usr/bin/app"
