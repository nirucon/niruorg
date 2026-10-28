from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal


class TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class TaskWorker(QRunnable):
    """Run one callable outside the GUI thread and report its result once."""

    def __init__(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = TaskSignals()
        self.setAutoDelete(False)

    def run(self) -> None:
        try:
            result = self.function(*self.args, **self.kwargs)
        except Exception as error:
            detail = str(error).strip() or error.__class__.__name__
            traceback.print_exc()
            self.signals.failed.emit(detail)
            return
        self.signals.done.emit(result)
