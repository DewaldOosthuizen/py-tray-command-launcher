# SPDX-License-Identifier: GPL-3.0-or-later
"""ProcessTracker — owns the map of in-flight QProcess handles and their count."""

from PyQt6.QtCore import QObject, pyqtSignal


class ProcessTracker(QObject):
    """Owns the map of in-flight QProcess handles and their count."""

    process_count_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._processes: dict = {}

    def add(self, proc_id: str, process) -> None:
        """Register a running process under proc_id and emit the new count."""
        self._processes[proc_id] = process
        self.process_count_changed.emit(self.count())

    def track(self, process) -> str:
        """Register *process* under a freshly generated id and return that id.

        Convenience wrapper around :meth:`add` for callers that don't need
        to choose their own process id (the common case).
        """
        import uuid

        proc_id = str(uuid.uuid4())
        self.add(proc_id, process)
        return proc_id

    def remove(self, proc_id: str) -> None:
        """Remove a process (no-op if proc_id is unknown) and emit the new count."""
        self._processes.pop(proc_id, None)
        self.process_count_changed.emit(self.count())

    def count(self) -> int:
        """Return the number of currently tracked processes."""
        return len(self._processes)

    @property
    def processes(self) -> dict:
        """Read-only view for callers that still need direct access (e.g. CommandManagerDialog)."""
        return self._processes
