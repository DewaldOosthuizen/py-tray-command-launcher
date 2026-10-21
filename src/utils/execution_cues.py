# SPDX-License-Identifier: GPL-3.0-or-later
"""Presentation helpers for command execution metadata."""

from collections.abc import Mapping
from typing import Any

_CUE_FLAGS = (
    ("confirm", "Confirmation required", "Confirm"),
    ("prompt", "Input required", "Input"),
    ("showOutput", "Output shown", "Output"),
)


def execution_cues(command: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Return user-facing execution cues without modifying the command payload.

    Args:
        command: Command metadata containing optional execution flags.

    Returns:
        Ordered confirmation, input, and output cue labels.
    """
    if not isinstance(command, Mapping):
        return ()
    return tuple(
        description for flag, description, _compact in _CUE_FLAGS if bool(command.get(flag))
    )


def format_execution_cues(command: Mapping[str, Any] | None, *, concise: bool = False) -> str:
    """Format command execution cues for visible and accessible UI labels.

    Args:
        command: Command metadata containing optional execution flags.
        concise: Use short labels suitable for compact tray-menu entries.

    Returns:
        Cue labels joined with a middle dot, or an empty string when no cue applies.
    """
    labels = execution_cues(command)
    if concise:
        compact = {description: short for _flag, description, short in _CUE_FLAGS}
        labels = tuple(compact[label] for label in labels)
    return " · ".join(labels)


def describe_execution_cues(command: Mapping[str, Any] | None) -> str:
    """Return a semicolon-separated accessibility description of execution cues."""
    return "; ".join(execution_cues(command))
