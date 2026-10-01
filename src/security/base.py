"""
Base interface for security checks. Every check inspects the
ExecutionTrace (+ config/test_case) and returns zero or more
SecurityFinding objects (empty list = no violations found).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List

from src.core.trace import ExecutionTrace
from src.security.models import SecurityFinding


def redact(value: str, keep: int = 4) -> str:
    """Redact a sensitive string, keeping only a short prefix for context."""
    if value is None:
        return ""
    value = str(value)
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "..." + "[REDACTED]"


class BaseSecurityCheck(ABC):
    category: str = "base"

    @abstractmethod
    def check(self, trace: ExecutionTrace, agent_config: Any, test_case: Any) -> List[SecurityFinding]:
        raise NotImplementedError
