#!/usr/bin/env python3
"""Benchmark startup time: process start to QSystemTrayIcon shown."""
import os
import subprocess
import sys
import time

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARKER = "TRAY_ICON_SHOWN"
TIMEOUT = 30.0

start = time.perf_counter()
proc = subprocess.Popen(
    [sys.executable, "src/main.py"],
    cwd=root,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
    bufsize=1,
)
elapsed = None
try:
    deadline = start + TIMEOUT
    if proc.stdout is not None:
        for line in proc.stdout:
            if MARKER in line:
                elapsed = time.perf_counter() - start
                break
            if time.perf_counter() > deadline:
                break
except Exception as exc:  # pragma: no cover - defensive
    print(f"benchmark_startup: {exc}", file=sys.stderr)
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

if elapsed is None:
    print("Startup: tray icon not shown within timeout", file=sys.stderr)
    sys.exit(1)
print(f"Startup elapsed (process start to QSystemTrayIcon shown): {elapsed:.3f}s")
