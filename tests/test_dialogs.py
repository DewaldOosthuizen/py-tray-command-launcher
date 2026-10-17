# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock, patch

import pytest

from utils import dialogs


def _configure_message_box():
    message_box = MagicMock()
    message_box.StandardButton.Yes = 1
    message_box.StandardButton.No = 2
    message_box.StandardButton.NoButton = 0
    return message_box


def test_show_info_dispatches_information_message():
    message_box = _configure_message_box()
    with patch.object(dialogs, "QMessageBox", message_box):
        dialogs.show_info("parent", "Title", "Message")
    message_box.information.assert_called_once_with("parent", "Title", "Message")


def test_show_warning_dispatches_warning_message():
    message_box = _configure_message_box()
    with patch.object(dialogs, "QMessageBox", message_box):
        dialogs.show_warning("parent", "Title", "Message")
    message_box.warning.assert_called_once_with("parent", "Title", "Message")


def test_show_error_dispatches_critical_message():
    message_box = _configure_message_box()
    with patch.object(dialogs, "QMessageBox", message_box):
        dialogs.show_error("parent", "Title", "Message")
    message_box.critical.assert_called_once_with("parent", "Title", "Message")


def test_confirm_action_uses_no_button_by_default_and_returns_yes_result():
    message_box = _configure_message_box()
    message_box.question.return_value = 1
    with patch.object(dialogs, "QMessageBox", message_box):
        result = dialogs.confirm_action("parent", "Title", "Message")
    assert result is True
    message_box.question.assert_called_once_with("parent", "Title", "Message", 3, 0)


def test_confirm_action_returns_false_for_no_result_and_uses_explicit_default():
    message_box = _configure_message_box()
    message_box.question.return_value = 2
    with patch.object(dialogs, "QMessageBox", message_box):
        result = dialogs.confirm_action("parent", "Title", "Message", default_button=2)
    assert result is False
    message_box.question.assert_called_once_with("parent", "Title", "Message", 3, 2)


@pytest.mark.parametrize("initial_text", ["", "prefilled"])
def test_prompt_text_forwards_initial_text_and_returns_qt_result(initial_text):
    qt_result = ("typed", True)
    input_dialog = MagicMock()
    input_dialog.getText.return_value = qt_result
    with patch.object(dialogs, "QInputDialog", input_dialog):
        result = dialogs.prompt_text("parent", "Title", "Prompt", initial_text=initial_text)
    assert result is qt_result
    input_dialog.getText.assert_called_once_with("parent", "Title", "Prompt", text=initial_text)


def test_confirm_execute_preserves_existing_prompt_and_no_default():
    with patch.object(dialogs, "confirm_action", return_value=True) as confirm:
        result = dialogs.confirm_execute("echo hello")
    assert result is True
    confirm.assert_called_once_with(
        None,
        "Confirmation",
        'Are you sure you want to execute "echo hello"?',
        default_button=dialogs.QMessageBox.StandardButton.No,
    )


def test_confirm_execute_without_command_does_not_show_dialog():
    with patch.object(dialogs, "confirm_action") as confirm:
        result = dialogs.confirm_execute()
    assert result is None
    confirm.assert_not_called()


def test_confirm_exit_preserves_existing_prompt_and_no_default():
    with patch.object(dialogs, "confirm_action", return_value=False) as confirm:
        result = dialogs.confirm_exit()
    assert result is False
    confirm.assert_called_once_with(
        None,
        "Exit Confirmation",
        "Are you sure you want to exit?",
        default_button=dialogs.QMessageBox.StandardButton.No,
    )


def test_show_error_and_raise_uses_shared_error_helper():
    with patch.object(dialogs, "show_error") as show_error:
        with pytest.raises(ValueError, match="failure"):
            dialogs.show_error_and_raise("failure")
    show_error.assert_called_once_with(None, "Error", "failure")
