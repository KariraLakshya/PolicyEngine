from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class ConversationMessage:
    role: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class Conversation:
    id: str = field(default_factory=lambda: str(uuid4()))
    messages: list[ConversationMessage] = field(default_factory=list)
    paused: bool = False
    waiting_approval_id: str | None = None

    def add_message(
        self,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.messages.append(
            ConversationMessage(role=role, content=content, metadata=metadata or {})
        )

    def token_count(self) -> int:
        # Deliberately simple for now; good enough for policy/audit accounting.
        return sum(len(message.content.split()) for message in self.messages)

    def context_snippet(self, limit: int = 240) -> str:
        text = "\n".join(f"{message.role}: {message.content}" for message in self.messages)
        return text[-limit:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "paused": self.paused,
            "waiting_approval_id": self.waiting_approval_id,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    "metadata": message.metadata,
                    "created_at": message.created_at,
                }
                for message in self.messages
            ],
        }
