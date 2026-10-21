# SPDX-License-Identifier: GPL-3.0-or-later
"""Execution cues remain a presentation derived from command metadata."""

import pytest

from utils.execution_cues import execution_cues, format_execution_cues


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        ({}, ()),
        ({"confirm": True}, ("Confirmation required",)),
        ({"prompt": "Enter a host"}, ("Input required",)),
        ({"showOutput": True}, ("Output shown",)),
        (
            {"confirm": True, "prompt": "Enter a host", "showOutput": True},
            ("Confirmation required", "Input required", "Output shown"),
        ),
        ({"confirm": False, "prompt": "", "showOutput": False}, ()),
    ],
)
def test_execution_cues_derive_only_from_execution_metadata(metadata, expected):
    assert execution_cues(metadata) == expected


def test_format_execution_cues_uses_concise_visible_separator():
    assert format_execution_cues(
        {"confirm": True, "prompt": "Input", "showOutput": True}
    ) == "Confirmation required · Input required · Output shown"
    assert format_execution_cues({}) == ""


def test_execution_cues_do_not_mutate_command_payload():
    command = {
        "group": "System",
        "label": "Run exactly as named",
        "command": "tool --flag",
        "confirm": True,
        "prompt": "Input",
        "showOutput": True,
    }
    original = command.copy()

    execution_cues(command)
    format_execution_cues(command)

    assert command == original
