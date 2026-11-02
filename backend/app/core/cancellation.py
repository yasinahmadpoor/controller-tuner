from __future__ import annotations


class JobCancelled(BaseException):
    """Raised by a cooperative progress callback when a job is cancelled.

    Inherits from ``BaseException`` so the engine's broad ``except Exception``
    around user callbacks does not swallow the cancellation signal.
    """
