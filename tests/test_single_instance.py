# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for SingleInstanceChecker.

Covers:
  - is_pid_running with valid/invalid/dead PIDs
  - acquire_lock PID file write + OSError logging
  - Wayland headless detection (DISPLAY and WAYLAND_DISPLAY)
  - force_unlock / cleanup OSError logging (not silently swallowed)
"""

import errno
import os
import sys
import threading
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Stub PyQt6 symbols that single_instance.py imports at module level.
for _mod in ["PyQt6", "PyQt6.QtCore", "PyQt6.QtWidgets"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)
_qc = sys.modules["PyQt6.QtCore"]
# QSharedMemory stub — give it create/attach/detach/isAttached methods
_QSM = MagicMock(name="QSharedMemory")
_qc.QSharedMemory = _QSM
_qw = sys.modules["PyQt6.QtWidgets"]
_qapp = MagicMock(name="QApplication")
_qapp.instance = MagicMock(return_value=None)
_qw.QApplication = _qapp
_syms_to_stub = [
    "QMessageBox",
    "QLabel",
    "QVBoxLayout",
    "QHBoxLayout",
    "QPushButton",
    "QDialog",
    "QWidget",
]
_saved_qw_attrs = {s: getattr(_qw, s, None) for s in _syms_to_stub}
for _sym in _syms_to_stub:
    setattr(_qw, _sym, MagicMock)

from utils.single_instance import SingleInstanceChecker

# Restore widget stubs so subsequent UI tests still receive the conftest _QWidget stubs.
for _sym, _val in _saved_qw_attrs.items():
    if _val is not None:
        setattr(_qw, _sym, _val)
    else:
        try:
            delattr(_qw, _sym)
        except AttributeError:
            pass


def _make_checker(key="test-key", pidfile=None):
    """Return a SingleInstanceChecker with a fresh MagicMock shared_memory."""
    checker = SingleInstanceChecker(key=key, pidfile=pidfile)
    # Replace the real (stubbed) QSharedMemory instance with a plain MagicMock
    # so we can control attach/create/isAttached per test.
    checker.shared_memory = MagicMock()
    return checker


class _SharedMemoryRegistry:
    """Model Qt shared-memory ownership and last-detach cleanup."""

    def __init__(self, exists=False, references=0):
        self.lock = threading.Lock()
        self.exists = exists
        self.references = references


class _SharedMemory:
    def __init__(self, registry):
        self.registry = registry
        self.attached = False

    def create(self, size):
        del size
        with self.registry.lock:
            if self.registry.exists:
                return False
            self.registry.exists = True
            self.registry.references = 1
            self.attached = True
            return True

    def attach(self):
        with self.registry.lock:
            if not self.registry.exists:
                return False
            self.registry.references += 1
            self.attached = True
            return True

    def detach(self):
        with self.registry.lock:
            if not self.attached:
                return False
            self.registry.references -= 1
            self.attached = False
            if self.registry.references == 0:
                self.registry.exists = False
            return True

    def isAttached(self):
        return self.attached


def _make_registered_checker(registry, pidfile=None):
    checker = _make_checker(pidfile=pidfile)
    checker.shared_memory = _SharedMemory(registry)
    return checker


# ---------------------------------------------------------------------------
# is_pid_running
# ---------------------------------------------------------------------------


class TestIsPidRunning:
    def test_own_pid_is_running(self):
        checker = _make_checker()
        assert checker.is_pid_running(os.getpid()) is True

    def test_negative_pid_returns_false(self):
        assert _make_checker().is_pid_running(-1) is False

    def test_zero_pid_returns_false(self):
        assert _make_checker().is_pid_running(0) is False

    def test_non_numeric_returns_false(self):
        assert _make_checker().is_pid_running("not-a-pid") is False

    def test_dead_pid_returns_false(self):
        assert _make_checker().is_pid_running(99999999) is False


# ---------------------------------------------------------------------------
# acquire_lock – PID file handling
# ---------------------------------------------------------------------------


class TestAcquireLock:
    def test_writes_pid_file_on_success(self, tmp_path):
        pidfile = str(tmp_path / "test.pid")
        checker = _make_checker(key="lock-write", pidfile=pidfile)
        checker.shared_memory.attach.return_value = False
        checker.shared_memory.create.return_value = True

        result = checker.acquire_lock()

        assert result is True
        assert Path(pidfile).read_text().strip() == str(os.getpid())

    def test_pid_file_oserror_is_logged_not_swallowed(self, tmp_path):
        """OSError on PID file write must be logged, not silently ignored."""
        pidfile = str(tmp_path / "test.pid")
        checker = _make_checker(key="lock-oserror", pidfile=pidfile)
        checker.shared_memory.attach.return_value = False
        checker.shared_memory.create.return_value = True

        with patch(
            "utils.single_instance.tempfile.NamedTemporaryFile", side_effect=OSError("disk full")
        ):
            with patch("utils.single_instance.logger") as mock_logger:
                result = checker.acquire_lock()

        assert result is True  # lock acquired even if PID file write fails
        mock_logger.warning.assert_called_once()
        warning_msg = str(mock_logger.warning.call_args)
        assert "disk full" in warning_msg

    def test_returns_false_when_already_locked(self):
        checker = _make_checker(key="lock-taken")
        checker.shared_memory.create.return_value = False
        checker.shared_memory.attach.return_value = True
        checker._is_stale_lock = MagicMock(return_value=False)

        result = checker.acquire_lock()

        assert result is False

    def test_live_pid_in_pidfile_keeps_lock(self, tmp_path):
        pidfile = tmp_path / "app.pid"
        pidfile.write_text(str(os.getpid()))
        checker = _make_checker(pidfile=str(pidfile))
        checker.shared_memory.attach.return_value = True

        assert checker.is_another_instance_running() is True

    def test_dead_pid_in_pidfile_is_recovered_as_stale(self, tmp_path):
        """A crashed owner can be replaced only after the orphan is detached."""
        pidfile = tmp_path / "app.pid"
        pidfile.write_text("999999999")
        registry = _SharedMemoryRegistry(exists=True)
        checker = _make_registered_checker(registry, pidfile=str(pidfile))
        with patch.object(checker, "is_pid_running", return_value=False):
            assert checker.acquire_lock() is True
        assert pidfile.read_text() == str(os.getpid())
        assert registry.exists is True
        assert registry.references == 1

    def test_losing_stale_recovery_preserves_contenders_pid(self, tmp_path):
        pidfile = tmp_path / "app.pid"
        pidfile.write_text("999999999")
        registry = _SharedMemoryRegistry(exists=True)
        checker = _make_registered_checker(registry, pidfile=str(pidfile))

        def contender_wins(_pid):
            with registry.lock:
                registry.references += 1
            pidfile.write_text("424242")
            return False

        with patch.object(checker, "is_pid_running", side_effect=contender_wins):
            assert checker.acquire_lock() is False

        assert pidfile.read_text() == "424242"
        assert registry.exists is True
        assert registry.references == 1

    def test_probe_only_treats_confirmed_missing_process_as_stale(self, tmp_path):
        pidfile = tmp_path / "app.pid"
        cases = [
            ("live", str(os.getpid()), None, False),
            ("dead", "45678", OSError(errno.ESRCH, "no process"), True),
            ("permission denied", "45678", OSError(errno.EPERM, "denied"), False),
            ("ambiguous error", "45678", OSError(errno.EIO, "probe failed"), False),
            ("out-of-range pid", "9" * 100, OverflowError("pid out of range"), False),
        ]
        for name, value, error, expected_acquired in cases:
            pidfile.write_text(value)
            registry = _SharedMemoryRegistry(exists=True)
            checker = _make_registered_checker(registry, pidfile=str(pidfile))
            with patch("utils.single_instance.os.kill", side_effect=error):
                assert checker.acquire_lock() is expected_acquired, name

    def test_malformed_and_unreadable_pid_are_not_recovered(self, tmp_path):
        pidfile = tmp_path / "app.pid"
        registry = _SharedMemoryRegistry(exists=True, references=1)
        checker = _make_registered_checker(registry, pidfile=str(pidfile))
        pidfile.write_text("not-a-pid")
        assert checker.acquire_lock() is False
        assert registry.exists is True

        pidfile.unlink()
        checker = _make_registered_checker(registry, pidfile=str(pidfile))
        with patch("builtins.open", side_effect=PermissionError("unreadable")):
            assert checker.acquire_lock() is False
        assert registry.exists is True

    def test_pid_is_atomically_replaced_only_after_create_wins(self, tmp_path):
        pidfile = tmp_path / "app.pid"
        pidfile.write_text("prior-complete-pid")
        checker = _make_checker(pidfile=str(pidfile))
        checker.shared_memory.create.return_value = True

        original_replace = os.replace

        def verify_replace(temp_path, destination):
            temp_path = Path(temp_path)
            assert temp_path.parent == pidfile.parent
            assert temp_path.read_text() == str(os.getpid())
            assert Path(destination).read_text() == "prior-complete-pid"
            original_replace(temp_path, destination)

        with patch("utils.single_instance.os.replace", side_effect=verify_replace) as replace:
            assert checker.acquire_lock() is True
        replace.assert_called_once()
        assert pidfile.read_text() == str(os.getpid())
        assert list(tmp_path.iterdir()) == [pidfile]

    def test_replace_failure_keeps_prior_pid_and_cleans_temporary_file(self, tmp_path, caplog):
        pidfile = tmp_path / "app.pid"
        pidfile.write_text("prior-complete-pid")
        checker = _make_checker(pidfile=str(pidfile))
        checker.shared_memory.create.return_value = True

        with patch("utils.single_instance.os.replace", side_effect=OSError("rename failed")):
            assert checker.acquire_lock() is True

        assert pidfile.read_text() == "prior-complete-pid"
        assert list(tmp_path.iterdir()) == [pidfile]
        assert "rename failed" in caplog.text

    def test_contended_acquisition_does_not_replace_pid(self, tmp_path):
        pidfile = tmp_path / "app.pid"
        pidfile.write_text("winner-pid")
        checker = _make_checker(pidfile=str(pidfile))
        checker.shared_memory.create.return_value = False
        checker.shared_memory.attach.return_value = False

        with patch("utils.single_instance.os.replace") as replace:
            assert checker.acquire_lock() is False
        replace.assert_not_called()
        assert pidfile.read_text() == "winner-pid"

    def test_concurrent_acquisition_has_one_winner_and_keeps_its_pid(self, tmp_path):
        pidfile = tmp_path / "app.pid"
        registry = _SharedMemoryRegistry()
        barrier = threading.Barrier(8)

        def acquire():
            checker = _make_registered_checker(registry, pidfile=str(pidfile))
            barrier.wait()
            return checker, checker.acquire_lock()

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: acquire(), range(8)))

        winners = [checker for checker, success in results if success]
        assert len(winners) == 1
        assert pidfile.read_text() == str(os.getpid())
        assert registry.exists is True
        assert registry.references == 1


# ---------------------------------------------------------------------------
# Headless / Wayland detection
# ---------------------------------------------------------------------------


class TestHeadlessDetection:
    """These tests verify the headless-detection logic inline (pure env checks)."""

    @staticmethod
    def _is_headless(qt_platform, display=None, wayland=None):
        env = {"QT_QPA_PLATFORM": qt_platform}
        if display:
            env["DISPLAY"] = display
        if wayland:
            env["WAYLAND_DISPLAY"] = wayland
        # Remove vars not set
        strip = [k for k in ("DISPLAY", "WAYLAND_DISPLAY") if k not in env]
        clean = {k: v for k, v in os.environ.items() if k not in strip}
        clean.update(env)
        with patch.dict(os.environ, clean, clear=True):
            plat = os.environ.get("QT_QPA_PLATFORM", "").lower()
            return plat == "offscreen" or (
                not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")
            )

    def test_x11_only_is_not_headless(self):
        assert self._is_headless("xcb", display=":0") is False

    def test_wayland_only_is_not_headless(self):
        assert self._is_headless("wayland", wayland="wayland-0") is False

    def test_both_displays_not_headless(self):
        assert self._is_headless("xcb", display=":0", wayland="wayland-0") is False

    def test_no_display_no_wayland_is_headless(self):
        assert self._is_headless("xcb") is True

    def test_offscreen_platform_is_always_headless(self):
        assert self._is_headless("offscreen", display=":0", wayland="wayland-0") is True


# ---------------------------------------------------------------------------
# force_unlock / cleanup — OSError must be logged, not swallowed
# ---------------------------------------------------------------------------


class TestForceUnlockLifecycle:
    def test_force_unlock_clears_orphan_from_unattached_checker(self, tmp_path):
        pidfile = tmp_path / "orphan.pid"
        pidfile.write_text("old-pid")
        registry = _SharedMemoryRegistry(exists=True)
        checker = _make_registered_checker(registry, pidfile=str(pidfile))

        checker.force_unlock()

        assert checker.shared_memory.isAttached() is False
        assert registry.exists is False
        assert pidfile.read_text() == "old-pid"
        assert checker.acquire_lock() is True
        assert pidfile.read_text() == str(os.getpid())

    def test_force_unlock_does_not_break_live_owner(self, tmp_path):
        pidfile = tmp_path / "live.pid"
        pidfile.write_text("live-owner")
        registry = _SharedMemoryRegistry(exists=True, references=1)
        checker = _make_registered_checker(registry, pidfile=str(pidfile))

        checker.force_unlock()

        assert registry.exists is True
        assert registry.references == 1
        assert pidfile.read_text() == "live-owner"
        assert checker.acquire_lock() is False

    def test_cleanup_detaches_without_unlinking_pid(self, tmp_path):
        pidfile = tmp_path / "owner.pid"
        pidfile.write_text("owner-pid")
        registry = _SharedMemoryRegistry()
        checker = _make_registered_checker(registry, pidfile=str(pidfile))
        assert checker.acquire_lock() is True

        checker.cleanup()

        assert registry.exists is False
        assert pidfile.read_text() == str(os.getpid())
