import json
from typing import Any, Dict, List, Optional

from src.core.config_models import AgentConfig, TestCase
from src.core.trace import (
    ExecutionTrace,
    LLMCallEvent,
    ToolCallEvent,
    ToolErrorEvent,
    RunErrorEvent,
    EventType,
)
from src.observability.cost import CostCalculator
from src.observability.latency import (
    calculate_duration_ms,
    compute_step_latencies,
    parse_timestamp,
)
from src.observability.models import ModelPricingConfig, RunMetrics, RunStatus
from src.observability.token_usage import extract_and_aggregate_tokens


class ObservabilityEngine:
    def __init__(
        self,
        pricing_catalog: Optional[Dict[str, ModelPricingConfig]] = None,
    ):
        self.cost_calculator = CostCalculator(pricing_catalog=pricing_catalog)

    def analyze(
        self,
        trace: ExecutionTrace,
        config: Optional[AgentConfig] = None,
        test_case: Optional[TestCase] = None,
    ) -> RunMetrics:

        duration = calculate_duration_ms(
            trace.started_at,
            trace.completed_at,
        )

        start_dt = parse_timestamp(trace.started_at)
        completed_dt = parse_timestamp(trace.completed_at)

        step_metrics = compute_step_latencies(trace.events)

        llm_call_count = 0
        tool_call_count = 0
        tool_error_count = 0
        llm_error_count = 0

        # Store complete tool execution information for the UI.
        tool_calls: List[Dict[str, Any]] = []
        tool_errors: List[Dict[str, Any]] = []

        tool_signatures: List[str] = []

        for event in trace.events:
            e_type = getattr(event, "type", None)

            # -------------------------
            # LLM CALL
            # -------------------------
            if (
                isinstance(event, LLMCallEvent)
                or e_type == EventType.LLM_CALL
                or e_type == "llm_call"
            ):
                llm_call_count += 1

            # -------------------------
            # TOOL CALL
            # -------------------------
            elif (
                isinstance(event, ToolCallEvent)
                or e_type == EventType.TOOL_CALL
                or e_type == "tool_call"
            ):
                tool_call_count += 1

                tool_name = getattr(event, "tool_name", "")
                arguments = getattr(event, "arguments", {})

                try:
                    args_str = json.dumps(
                        arguments,
                        sort_keys=True,
                    )
                except Exception:
                    args_str = str(arguments)

                tool_signatures.append(
                    f"{tool_name}:{args_str}"
                )

                # Save actual tool call for frontend.
                tool_calls.append(
                    {
                        "tool_name": tool_name,
                        "arguments": arguments,
                    }
                )

            # -------------------------
            # TOOL ERROR
            # -------------------------
            elif (
                isinstance(event, ToolErrorEvent)
                or e_type == EventType.TOOL_ERROR
                or e_type == "tool_error"
            ):
                tool_error_count += 1

                tool_errors.append(
                    {
                        "tool_name": getattr(
                            event,
                            "tool_name",
                            "",
                        ),
                        "error": getattr(
                            event,
                            "error",
                            None,
                        ),
                    }
                )

            # -------------------------
            # RUN ERROR
            # -------------------------
            elif (
                isinstance(event, RunErrorEvent)
                or e_type == EventType.RUN_ERROR
                or e_type == "run_error"
            ):
                llm_error_count += 1

        # -------------------------
        # REPEATED TOOL CALLS
        # -------------------------
        repeated_tool_call_count = 0
        seen_signatures = set()

        repeated_tool_calls: List[Dict[str, Any]] = []

        for index, sig in enumerate(tool_signatures):
            if sig in seen_signatures:
                repeated_tool_call_count += 1

                if index < len(tool_calls):
                    repeated_tool_calls.append(
                        tool_calls[index]
                    )
            else:
                seen_signatures.add(sig)

        # -------------------------
        # RUN STATUS
        # -------------------------
        if trace.error:
            status = RunStatus.ERROR
        elif tool_error_count > 0 or llm_error_count > 0:
            status = RunStatus.FAILED
        else:
            status = RunStatus.SUCCESS

        # -------------------------
        # TOKEN METRICS
        # -------------------------
        token_metrics = extract_and_aggregate_tokens(trace)

        # ---------------------------------------------------------
        # MODEL RESOLUTION
        # Checks:
        # config -> trace -> LLM events
        # ---------------------------------------------------------
        model_name = None

        if config and getattr(config, "llm", None):
            model_name = getattr(
                config.llm,
                "model",
                None,
            )

        if not model_name and hasattr(trace, "model"):
            model_name = getattr(
                trace,
                "model",
                None,
            )

        if not model_name:
            for event in trace.events:
                e_type = getattr(event, "type", None)

                if (
                    isinstance(event, LLMCallEvent)
                    or e_type in (
                        EventType.LLM_CALL,
                        "llm_call",
                    )
                ):
                    m = getattr(
                        event,
                        "model",
                        None,
                    )

                    if (
                        not m
                        and hasattr(event, "response")
                        and isinstance(event.response, dict)
                    ):
                        m = event.response.get("model")

                    if (
                        not m
                        and hasattr(event, "metadata")
                        and isinstance(event.metadata, dict)
                    ):
                        m = event.metadata.get("model")

                    if m:
                        model_name = m
                        break

        # -------------------------
        # COST
        # -------------------------
        cost_breakdown = self.cost_calculator.calculate_cost(
            model_name,
            token_metrics,
        )

        # -------------------------
        # FINAL METRICS
        # -------------------------
        return RunMetrics(
            run_id=trace.run_id,
            started_at=start_dt,
            completed_at=completed_dt,
            duration_ms=duration,
            status=status,

            llm_call_count=llm_call_count,
            tool_call_count=tool_call_count,
            tool_error_count=tool_error_count,
            llm_error_count=llm_error_count,
            repeated_tool_call_count=repeated_tool_call_count,

            # NEW: actual execution data
            tool_calls=tool_calls,
            tool_errors=tool_errors,
            repeated_tool_calls=repeated_tool_calls,

            tokens=token_metrics,
            cost=cost_breakdown,
            step_metrics=step_metrics,

            metadata={
                "agent_id": (
                    getattr(trace, "agent_id", "")
                    or (
                        getattr(config, "id", "")
                        if config
                        else ""
                    )
                ),
                "test_case_id": (
                    getattr(trace, "test_case_id", "")
                    or (
                        getattr(test_case, "id", "")
                        if test_case
                        else ""
                    )
                ),
            },
        )