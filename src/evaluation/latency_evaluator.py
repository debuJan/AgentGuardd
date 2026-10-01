"""Latency-budget evaluator.

Enforces ``test_case.max_latency_ms``: the wall-clock span of the trace
(first to last event timestamp) must not exceed the configured budget.

Timestamps are ISO strings recorded when each event was created, so this
measures real elapsed time including LLM and tool latency. If the trace
has no parseable timestamps, the check skips honestly rather than
guessing.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from src.core.trace import ExecutionTrace
from src.evaluation.base import BaseEvaluator
from src.evaluation.models import EvaluationCheck


def _parse(ts: Any) -> Optional[datetime]:
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return None
    return None


def trace_duration_ms(trace: ExecutionTrace) -> Optional[float]:
    stamps: List[datetime] = []
    for event in trace.events:
        parsed = _parse(getattr(event, "timestamp", None))
        if parsed is not None:
            stamps.append(parsed)
    if len(stamps) < 2:
        return None
    delta = (max(stamps) - min(stamps)).total_seconds() * 1000.0
    return max(0.0, delta)


class MaxLatencyEvaluator(BaseEvaluator):
    """Did the run complete within the configured max_latency_ms budget?"""

    name = "max_latency"

    def evaluate(
        self,
        trace: ExecutionTrace,
        agent_config: Any,
        test_case: Any,
    ) -> EvaluationCheck:
        budget = getattr(test_case, "max_latency_ms", None)

        if budget is None:
            return self._check(
                True,
                1.0,
                "No max_latency_ms configured; skipping.",
                {"skipped": True},
            )

        duration = trace_duration_ms(trace)
        if duration is None:
            return self._check(
                True,
                1.0,
                "Could not determine trace duration from event timestamps; skipping.",
                {"skipped": True, "reason": "no_parseable_timestamps"},
            )

        details = {"duration_ms": round(duration, 2), "max_latency_ms": budget}
        if duration <= budget:
            return self._check(
                True,
                1.0,
                f"Run completed within latency budget ({duration:.0f}ms <= {budget}ms).",
                details,
            )
        return self._check(
            False,
            0.0,
            f"Latency budget exceeded: {duration:.0f}ms > {budget}ms.",
            details,
        )
