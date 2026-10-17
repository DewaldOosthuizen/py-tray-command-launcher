# SPDX-License-Identifier: GPL-3.0-or-later

from PyQt6.QtWidgets import QInputDialog, QMessageBox


def show_error_and_raise(message):
    """Display an error dialog and raise ``ValueError`` with the same message.

    Args:
        message: Error text displayed and included in the raised exception.

    Raises:
        ValueError: Always, after the error dialog is displayed.
    """
    show_error(None, "Error", message)
    raise ValueError(message)


def confirm_execute(command=None):
    """Ask whether to execute a command, defaulting the dialog to No.

    Args:
        command: Command text included in the confirmation prompt.

    Returns:
        Whether the user selected Yes, or ``None`` when command is empty.
    """
    if command:
        return confirm_action(
            None,
            "Confirmation",
            f'Are you sure you want to execute "{command}"?',
            default_button=QMessageBox.StandardButton.No,
        )


def confirm_exit():
    """Ask whether to exit the application, defaulting the dialog to No.

    Returns:
        ``True`` if the user selected Yes; otherwise ``False``.
    """
    return confirm_action(
        None,
        "Exit Confirmation",
        "Are you sure you want to exit?",
        default_button=QMessageBox.StandardButton.No,
    )


def show_info(parent, title, message):
    """Display an information message.

    Args:
        parent: Parent widget for the dialog, or ``None``.
        title: Dialog title.
        message: Message text to display.

    Returns:
        ``None``.
    """
    QMessageBox.information(parent, title, message)


def show_warning(parent, title, message):
    """Display a warning message.

    Args:
        parent: Parent widget for the dialog, or ``None``.
        title: Dialog title.
        message: Message text to display.

    Returns:
        ``None``.
    """
    QMessageBox.warning(parent, title, message)


def show_error(parent, title, message):
    """Display an error message.

    Args:
        parent: Parent widget for the dialog, or ``None``.
        title: Dialog title.
        message: Message text to display.

    Returns:
        ``None``.
    """
    QMessageBox.critical(parent, title, message)


def confirm_action(parent, title, message, default_button=None):
    """Ask a Yes/No question and return whether the user selected Yes.

    Args:
        parent: Parent widget for the dialog, or ``None``.
        title: Dialog title.
        message: Question text to display.
        default_button: Default button; defaults to ``NoButton``.

    Returns:
        ``True`` if the user selected Yes; otherwise ``False``.
    """
    default = default_button if default_button is not None else QMessageBox.StandardButton.NoButton
    reply = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        default,
    )
    return reply == QMessageBox.StandardButton.Yes


def prompt_text(parent, title, prompt, initial_text=""):
    """Display a text-input dialog and return Qt's ``(text, accepted)`` pair.

    Args:
        parent: Parent widget for the dialog, or ``None``.
        title: Dialog title.
        prompt: Prompt text displayed to the user.
        initial_text: Text prefilled in the input field.

    Returns:
        The ``(text, accepted)`` tuple returned by ``QInputDialog.getText``.
    """
    return QInputDialog.getText(parent, title, prompt, text=initial_text)
