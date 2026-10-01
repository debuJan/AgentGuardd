from src.core.trace import ExecutionTrace, LLMCallEvent, EventType
from src.observability.models import TokenMetrics, TokenStatus


def extract_and_aggregate_tokens(trace: ExecutionTrace) -> TokenMetrics:
    total_input = 0
    total_output = 0
    has_tokens = False

    for event in trace.events:
        # Robust event type check (isinstance OR EventType enum OR attribute presence)
        e_type = getattr(event, "type", None)
        is_llm = (
            isinstance(event, LLMCallEvent)
            or e_type == EventType.LLM_CALL
            or e_type == "llm_call"
            or (hasattr(EventType, "LLM_CALL") and e_type == getattr(EventType.LLM_CALL, "value", None))
            or (hasattr(event, "prompt_tokens") and hasattr(event, "completion_tokens"))
        )

        if is_llm:
            p_tok = getattr(event, "prompt_tokens", None)
            c_tok = getattr(event, "completion_tokens", None)
            if p_tok is not None or c_tok is not None:
                has_tokens = True
                total_input += p_tok or 0
                total_output += c_tok or 0

    if not has_tokens:
        return TokenMetrics(
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            status=TokenStatus.UNAVAILABLE,
        )

    return TokenMetrics(
        input_tokens=total_input,
        output_tokens=total_output,
        total_tokens=total_input + total_output,
        status=TokenStatus.MEASURED,
    )