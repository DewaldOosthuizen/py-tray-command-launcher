"""Regression tests for the repository's Makefile interface."""

from __future__ import annotations

import os
import re
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_TARGETS = ["install-dev", "lint", "test", "audit", "build"]


def test_help_lists_every_target_with_a_description() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    targets = {}
    for line in makefile.splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):.*$", line)
        if match and not match.group(1).startswith(".PHONY"):
            target = match.group(1)
            if target not in {".DEFAULT_GOAL"}:
                targets[target] = "##" in line

    result = subprocess.run(["make", "help"], cwd=ROOT, check=True, capture_output=True, text=True)
    help_targets = {
        line.split(maxsplit=1)[0]
        for line in result.stdout.splitlines()
        if line.startswith("  ") and line.strip()
    }

    assert targets
    assert all(targets.values()), "Every Make target must have a ## description"
    assert help_targets == set(targets)


def _make_with_recorder(
    tmp_path: Path, fail_target: str = ""
) -> tuple[subprocess.CompletedProcess[str], list[str], int]:
    recorder = tmp_path / "record-submake.py"
    state_file = tmp_path / "state.txt"
    events_file = tmp_path / "events.txt"
    recorder.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import fcntl
            import os
            import sys
            import time
            from pathlib import Path

            state = Path(os.environ["RECORDER_STATE"])
            events = Path(os.environ["RECORDER_EVENTS"])
            target = sys.argv[-1]
            with state.open("a+") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                stream.seek(0)
                active, maximum = map(int, (stream.read() or "0 0").split())
                active += 1
                maximum = max(active, maximum)
                stream.seek(0)
                stream.truncate()
                stream.write(f"{active} {maximum}")
                stream.flush()
                with events.open("a") as event_stream:
                    event_stream.write(f"start {target}\\n")
                fcntl.flock(stream, fcntl.LOCK_UN)

            time.sleep(0.05)
            with state.open("a+") as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                stream.seek(0)
                active, maximum = map(int, stream.read().split())
                stream.seek(0)
                stream.truncate()
                stream.write(f"{active - 1} {maximum}")
                stream.flush()
                with events.open("a") as event_stream:
                    event_stream.write(f"finish {target}\\n")
                fcntl.flock(stream, fcntl.LOCK_UN)
            sys.exit(1 if target == os.environ.get("FAIL_TARGET") else 0)
            """
        ),
        encoding="utf-8",
    )
    recorder.chmod(0o755)
    env = os.environ.copy()
    env.update(
        RECORDER_STATE=str(state_file),
        RECORDER_EVENTS=str(events_file),
        FAIL_TARGET=fail_target,
    )
    result = subprocess.run(
        ["make", "-j", "ci", f"MAKE={recorder}"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    events = events_file.read_text(encoding="utf-8").splitlines() if events_file.exists() else []
    maximum = int(state_file.read_text(encoding="utf-8").split()[1]) if state_file.exists() else 0
    return result, events, maximum


def test_ci_submakes_are_serial_and_stop_after_failure(tmp_path: Path) -> None:
    result, events, maximum = _make_with_recorder(tmp_path)

    assert result.returncode == 0, result.stderr
    assert events == [
        event for target in CI_TARGETS for event in (f"start {target}", f"finish {target}")
    ]
    assert maximum == 1


def test_ci_stops_after_failed_submake(tmp_path: Path) -> None:
    result, events, maximum = _make_with_recorder(tmp_path, "test")

    assert result.returncode != 0
    assert events == [
        "start install-dev",
        "finish install-dev",
        "start lint",
        "finish lint",
        "start test",
        "finish test",
    ]
    assert maximum == 1
