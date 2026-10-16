#!/usr/bin/env python3
"""Benchmark command search and, separately, app startup.

The search workload uses a deterministic 1,500-command corpus with representative
group/label names and a repeated 10-query cycle. ``--search-only`` runs the
microbenchmark without requiring a display; ``--startup-only`` measures only
process start through the tray-icon marker. The default runs both independently.
"""

import argparse
import os
import subprocess
import sys
import time

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

MARKER = "TRAY_ICON_SHOWN"
TIMEOUT = 30.0
SEARCH_CORPUS_SIZE = 1500
SEARCH_REPEATS = 30
SEARCH_QUERIES = (
    "terminal",
    "git status",
    "disk usage",
    "system logs",
    "network settings",
    "backup project",
    "update system",
    "show memory",
    "configure python",
    "zzzzunlikely",
)


def _build_search_corpus(size):
    """Create a deterministic corpus with representative command groups and labels."""
    groups = ("System", "Development", "Files", "Network", "Maintenance", "Projects")
    actions = (
        "Open",
        "Check",
        "Update",
        "Clean",
        "List",
        "Show",
        "Restart",
        "Start",
        "Stop",
        "Backup",
        "Restore",
        "Search",
        "Install",
        "Configure",
        "Remove",
    )
    targets = (
        "Terminal",
        "Editor",
        "Disk Usage",
        "Memory Usage",
        "Git Status",
        "Network Settings",
        "System Logs",
        "Python Environment",
        "Project Files",
        "Service Manager",
    )
    return [
        {
            "group": groups[index % len(groups)],
            "label": (
                f"{actions[(index // len(groups)) % len(actions)]} "
                f"{targets[(index // (len(groups) * len(actions))) % len(targets)]} "
                f"{index:04d}"
            ),
            "command": f"command-{index:04d}",
        }
        for index in range(size)
    ]


def benchmark_search():
    """Compare cached and uncached timings after checking result parity."""
    from modules.command_search import (
        clear_command_search_cache,
        command_search_cache_info,
        search_commands,
        search_commands_uncached,
    )

    corpus = _build_search_corpus(SEARCH_CORPUS_SIZE)
    workload = SEARCH_QUERIES * SEARCH_REPEATS

    clear_command_search_cache()
    for query in SEARCH_QUERIES:
        uncached_results = search_commands_uncached(query, corpus)
        cached_results = search_commands(query, corpus)
        if cached_results != uncached_results:
            raise AssertionError(f"Cached search results differ for query {query!r}")

    clear_command_search_cache()
    start = time.perf_counter()
    for query in workload:
        search_commands_uncached(query, corpus)
    uncached_elapsed = time.perf_counter() - start
    uncached_cache_info = command_search_cache_info()

    clear_command_search_cache()
    start = time.perf_counter()
    for query in workload:
        search_commands(query, corpus)
    cached_elapsed = time.perf_counter() - start
    cached_cache_info = command_search_cache_info()

    relative_improvement = (uncached_elapsed - cached_elapsed) / uncached_elapsed * 100
    relative_label = "improved" if relative_improvement > 0 else "regressed"
    if relative_improvement == 0:
        relative_label = "neutral"

    print("Search benchmark: shared command-search helper")
    print(f"  Corpus: {len(corpus)} representative commands")
    print(
        f"  Workload: {len(SEARCH_QUERIES)} queries repeated {SEARCH_REPEATS} times "
        f"({len(workload)} searches)"
    )
    print(f"  Uncached elapsed: {uncached_elapsed:.6f}s")
    print(f"  Uncached cache hits/misses: {uncached_cache_info.hits}/{uncached_cache_info.misses}")
    print(f"  Cached elapsed: {cached_elapsed:.6f}s")
    print(f"  Cached cache hits/misses: {cached_cache_info.hits}/{cached_cache_info.misses}")
    print(f"  Cached relative result: {relative_label} {relative_improvement:+.2f}%")
    return relative_improvement >= 0


def benchmark_startup():
    """Measure process startup through the tray-icon-shown marker."""
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
        return False
    print(f"Startup elapsed (process start to QSystemTrayIcon shown): {elapsed:.3f}s")
    return True


def main():
    """Run requested benchmark modes and return a failing status if either fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--search-only", action="store_true", help="run only the search benchmark")
    mode.add_argument("--startup-only", action="store_true", help="run only the startup benchmark")
    args = parser.parse_args()

    outcomes = []
    if not args.startup_only:
        outcomes.append(benchmark_search())
    if not args.search_only:
        outcomes.append(benchmark_startup())
    return 0 if all(outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
