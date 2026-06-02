"""Tests for AppDiscovery.clean_exec, build_launch_args, and is_windows_lnk_entry."""

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
