from datetime import datetime
from typing import List, Optional, Union
from src.core.trace import TraceEvent, LLMCallEvent, ToolCallEvent, ToolErrorEvent, RunErrorEvent
from src.observability.models import StepMetrics


def parse_timestamp(ts: Union[str, datetime, None]) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return None


def calculate_duration_ms(
        started_at: Union[str, datetime, None],
        completed_at: Union[str, datetime, None]
) -> Optional[float]:
    start_dt = parse_timestamp(started_at)
    end_dt = parse_timestamp(completed_at)
    if start_dt is None or end_dt is None:
        return None
    delta = (end_dt - start_dt).total_seconds() * 1000.0
    return max(0.0, delta)


def compute_step_latencies(events: List[TraceEvent]) -> List[StepMetrics]:
    """Approximate per-step latencies from event timestamps.

    A step's ``duration_ms`` is the gap between its own timestamp and the
    next event's timestamp — an *event-gap approximation*, not a measured
    execution time. Consequences:

    - It includes idle time between events (queueing, scheduling).
    - The last event has no successor, so its duration is None.
    - Events recorded out of order or with coarse clock resolution
      produce misleading gaps; treat these numbers as indicative only.
    """
    steps: List[StepMetrics] = []

    for idx, event in enumerate(events):
        started_dt = parse_timestamp(event.timestamp)
        completed_dt = None

        if started_dt and idx + 1 < len(events):
            completed_dt = parse_timestamp(events[idx + 1].timestamp)

        dur_ms = calculate_duration_ms(started_dt, completed_dt)

        event_name: Optional[str] = None
        error_msg: Optional[str] = None
        inp_tok: Optional[int] = None
        out_tok: Optional[int] = None
        tot_tok: Optional[int] = None

        if isinstance(event, LLMCallEvent):
            event_name = "llm_call"
            inp_tok = event.prompt_tokens
            out_tok = event.completion_tokens
            if inp_tok is not None and out_tok is not None:
                tot_tok = inp_tok + out_tok
        elif isinstance(event, ToolCallEvent):
            event_name = event.tool_name
        elif isinstance(event, ToolErrorEvent):
            event_name = event.tool_name
            error_msg = event.error
        elif isinstance(event, RunErrorEvent):
            error_msg = event.error

        step_status = "error" if error_msg else "success"

        # event.type is an EventType Enum
        e_type_str = event.type.value if hasattr(event.type, "value") else str(event.type)

        steps.append(
            StepMetrics(
                step_index=idx,
                event_type=e_type_str,
                event_name=event_name,
                started_at=started_dt,
                completed_at=completed_dt,
                duration_ms=dur_ms,
                status=step_status,
                input_tokens=inp_tok,
                output_tokens=out_tok,
                total_tokens=tot_tok,
                error_message=error_msg,
            )
        )
    return steps