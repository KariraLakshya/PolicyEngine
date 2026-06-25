from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPError(Exception):
    code: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_response(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "data": self.data,
            }
        }
