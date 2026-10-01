"""
Execution Trace models.

Strongly typed, reusable representation of a single agent run, captured
event-by-event so the (future) evaluation engine can analyze it.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventType(str, Enum):
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    FINAL_RESPONSE = "final_response"
    RUN_ERROR = "run_error"


class BaseEvent(BaseModel):
    type: EventType
    timestamp: str = Field(default_factory=_now)


class LLMCallEvent(BaseEvent):
    type: Literal[EventType.LLM_CALL] = EventType.LLM_CALL
    input: str
    output: Optional[str] = None
    tool_calls_requested: List[str] = Field(default_factory=list)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


class ToolCallEvent(BaseEvent):
    type: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolResultEvent(BaseEvent):
    type: Literal[EventType.TOOL_RESULT] = EventType.TOOL_RESULT
    tool_name: str
    result: Any = None


class ToolErrorEvent(BaseEvent):
    type: Literal[EventType.TOOL_ERROR] = EventType.TOOL_ERROR
    tool_name: str
    error: str


class FinalResponseEvent(BaseEvent):
    type: Literal[EventType.FINAL_RESPONSE] = EventType.FINAL_RESPONSE
    content: str


class RunErrorEvent(BaseEvent):
    type: Literal[EventType.RUN_ERROR] = EventType.RUN_ERROR
    error: str


TraceEvent = Union[
    LLMCallEvent,
    ToolCallEvent,
    ToolResultEvent,
    ToolErrorEvent,
    FinalResponseEvent,
    RunErrorEvent,
]


class ExecutionTrace(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    test_case_id: str
    started_at: str = Field(default_factory=_now)
    completed_at: Optional[str] = None
    events: List[TraceEvent] = Field(default_factory=list)
    final_response: Optional[str] = None
    error: Optional[str] = None

    # -- convenience helpers used by the runner -----------------------------

    def add_event(self, event: TraceEvent) -> None:
        self.events.append(event)

    def mark_complete(self, final_response: Optional[str] = None) -> None:
        self.completed_at = _now()
        if final_response is not None:
            self.final_response = final_response

    def mark_failed(self, error: str) -> None:
        self.completed_at = _now()
        self.error = error
        self.add_event(RunErrorEvent(error=error))

    def tool_call_names(self) -> List[str]:
        return [e.tool_name for e in self.events if isinstance(e, ToolCallEvent)]
