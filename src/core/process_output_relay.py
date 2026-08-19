# SPDX-License-Identifier: GPL-3.0-or-later
"""ProcessOutputRelay — streams a QProcess's stdout/stderr into an output tab.

Extracted from ``TrayApp.show_command_output`` so the stdout/stderr/error
wiring boilerplate is unit-testable in isolation and TrayApp only has to
construct the relay and supply a completion callback.
"""

import logging
import weakref

logger = logging.getLogger(__name__)


class ProcessOutputRelay:
    """Streams process stdout/stderr into an output window tab.

    Holds only a weak reference to the output window so a closed window
    does not keep the relay (or the process) alive.
    """

    def __init__(self, process, output_win, tab, command: str):
        self._process = process
        self._output_win_ref = weakref.ref(output_win)
        self._tab = tab
        self._command = command

    def wire(self, on_finished) -> None:
        """Connect stdout/stderr/finished/errorOccurred signals.

        ``on_finished`` is invoked with no arguments both when the process
        finishes normally and when it errors out.
        """
        process = self._process

        process.readyReadStandardOutput.connect(self._on_stdout)
        process.readyReadStandardError.connect(self._on_stderr)
        process.finished.connect(on_finished)
        process.errorOccurred.connect(lambda error: self._on_error(error, on_finished))

    def _on_stdout(self) -> None:
        output = self._process.readAllStandardOutput().data().decode(errors="replace")
        if not output:
            return
        self._append(output, "stdout")

    def _on_stderr(self) -> None:
        output = self._process.readAllStandardError().data().decode(errors="replace")
        if not output:
            return
        self._append(output, "stderr")

    def _on_error(self, error, on_finished) -> None:
        logger.error("QProcess error for command '%s': %s", self._command, error)
        self._append(f"\n[ERROR] Process error: {error}\n", "error", swallow=True)
        on_finished()

    def _append(self, text: str, stream: str, swallow: bool = False) -> None:
        win = self._output_win_ref()
        if win is None:
            return
        try:
            win.append_output(self._tab, text)
        except RuntimeError as exc:
            if swallow:
                return
            logger.debug("Output window destroyed before %s could be written: %s", stream, exc)
