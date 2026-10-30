"""UI runtime: runs the agent loop in a worker thread and queues approvals.

The web process and the agent never share the approval decision implicitly:
the agent's decide() blocks on a per-request Event until a human clicks
Approve or Reject in the browser. There is no timeout on that wait — the
approval gate is unbypassable, so a stalled human means a stalled agent,
never an auto-approved action.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field

from ..agent import AgentLoop, AgentReport
from ..approval import PlainLanguageDiff

logger = logging.getLogger("openxr_operator.ui.runtime")


@dataclass
class ApprovalRequest:
    id: str
    task: str
    diff: PlainLanguageDiff
    approved: bool = False
    event: threading.Event = field(default_factory=threading.Event, repr=False)


class UIRuntime:
    def __init__(self, loop: AgentLoop) -> None:
        self._loop = loop
        self._pending: dict[str, ApprovalRequest] = {}
        self._lock = threading.Lock()
        self._state = "idle"  # idle | running | done | error
        self._task = ""
        self._summary = ""
        self._error = ""

    def start_task(self, task: str) -> None:
        if self._state == "running":
            raise RuntimeError("a task is already running")
        if not task.strip():
            raise ValueError("task must not be empty")
        self._task = task
        self._summary = ""
        self._error = ""
        self._state = "running"
        threading.Thread(target=self._run, args=(task,), daemon=True).start()

    def _run(self, task: str) -> None:
        try:
            report: AgentReport = self._loop.run_task(task, decide=self._decide)
            self._summary = report.summary
            self._state = "done"
        except Exception as exc:  # logged; the UI shows an error state
            logger.exception("agent task failed")
            self._error = str(exc)
            self._state = "error"

    def _decide(self, diff: PlainLanguageDiff) -> bool:
        request = ApprovalRequest(id=uuid.uuid4().hex[:12], task=self._task, diff=diff)
        with self._lock:
            self._pending[request.id] = request
        request.event.wait()  # no timeout: the human gate cannot lapse
        with self._lock:
            self._pending.pop(request.id, None)
        return request.approved

    def pending(self) -> list[ApprovalRequest]:
        with self._lock:
            return list(self._pending.values())

    def decide(self, request_id: str, approved: bool) -> bool:
        with self._lock:
            request = self._pending.get(request_id)
            if request is None:
                return False
            request.approved = approved
            request.event.set()
            return True

    def status(self) -> dict[str, object]:
        return {
            "state": self._state,
            "task": self._task,
            "summary": self._summary,
            "error": self._error,
            "pending": [r.id for r in self.pending()],
        }
