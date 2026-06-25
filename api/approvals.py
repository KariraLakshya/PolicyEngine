from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Event, RLock
from typing import Any
from uuid import uuid4


@dataclass
class ApprovalRequest:
    conversation_id: str
    tool_call: dict[str, Any]
    context_snippet: str
    ttl_seconds: int
    id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "pending"
    decision: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    event: Event = field(default_factory=Event, repr=False)

    @property
    def expires_at(self) -> datetime:
        created = datetime.fromisoformat(self.created_at)
        return created + timedelta(seconds=self.ttl_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "tool_call": self.tool_call,
            "context_snippet": self.context_snippet,
            "status": self.status,
            "decision": self.decision,
            "created_at": self.created_at,
            "expires_at": self.expires_at.isoformat(),
        }


class ApprovalQueue:
    def __init__(self, ttl_seconds: int = 1800) -> None:
        self._ttl_seconds = ttl_seconds
        self._lock = RLock()
        self._requests: dict[str, ApprovalRequest] = {}

    def enqueue(
        self,
        *,
        conversation_id: str,
        tool_call: dict[str, Any],
        context_snippet: str,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            conversation_id=conversation_id,
            tool_call=tool_call,
            context_snippet=context_snippet,
            ttl_seconds=self._ttl_seconds,
        )

        with self._lock:
            self._requests[request.id] = request

        return request

    def decide(self, approval_id: str, decision: str) -> ApprovalRequest:
        if decision not in {"approved", "denied"}:
            raise ValueError("Decision must be approved or denied.")

        with self._lock:
            request = self._requests[approval_id]
            request.status = "decided"
            request.decision = decision
            request.event.set()
            return request

    def wait_for_decision(self, approval_id: str) -> str:
        with self._lock:
            request = self._requests[approval_id]

        decided = request.event.wait(timeout=request.ttl_seconds)
        if not decided:
            with self._lock:
                request.status = "timeout"
                request.decision = "denied"
            return "timeout"

        return request.decision or "denied"

    def pending(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)

        with self._lock:
            for request in self._requests.values():
                if request.status == "pending" and request.expires_at <= now:
                    request.status = "timeout"
                    request.decision = "denied"
                    request.event.set()

            return [
                request.to_dict()
                for request in self._requests.values()
                if request.status == "pending"
            ]
