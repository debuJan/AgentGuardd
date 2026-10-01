from datetime import datetime, timezone
import pytest

from src.core.config_models import AgentConfig, TestCase
from src.core.trace import (
    ExecutionTrace,
    LLMCallEvent,
    ToolCallEvent,
    ToolErrorEvent,
    RunErrorEvent,
)
from src.observability.engine import ObservabilityEngine
from src.observability.models import RunStatus, TokenStatus


def test_clean_run_metrics():
    t0 = "2026-08-12T12:00:00+00:00"
    t1 = "2026-08-12T12:00:02+00:00"

    trace = ExecutionTrace(
        run_id="run_clean",
        agent_id="agent_1",
        test_case_id="tc_1",
        started_at=t0,
        completed_at=t1,
        events=[
            LLMCallEvent(
                timestamp=t0,
                input="Hello",
                output="Hi",
                prompt_tokens=100,
                completion_tokens=50,
            )
        ],
    )
    engine = ObservabilityEngine()
    metrics = engine.analyze(trace)

    assert metrics.run_id == "run_clean"
    assert metrics.duration_ms == 2000.0
    assert metrics.status == RunStatus.SUCCESS
    assert metrics.llm_call_count == 1
    assert metrics.tool_call_count == 0
    assert metrics.repeated_tool_call_count == 0


def test_multiple_llm_and_tool_calls():
    t0 = "2026-08-12T12:00:00+00:00"
    t1 = "2026-08-12T12:00:01+00:00"
    t2 = "2026-08-12T12:00:05+00:00"

    trace = ExecutionTrace(
        run_id="run_multi",
        agent_id="agent_1",
        test_case_id="tc_1",
        started_at=t0,
        completed_at=t2,
        events=[
            LLMCallEvent(timestamp=t0, input="Prompt 1", output="Call tool"),
            ToolCallEvent(timestamp=t1, tool_name="get_order", arguments={"order_id": "123"}),
            LLMCallEvent(timestamp=t1, input="Tool result", output="Final answer"),
        ],
    )
    engine = ObservabilityEngine()
    metrics = engine.analyze(trace)

    assert metrics.llm_call_count == 2
    assert metrics.tool_call_count == 1
    assert metrics.duration_ms == 5000.0


def test_tool_and_llm_errors():
    t0 = "2026-08-12T12:00:00+00:00"
    t1 = "2026-08-12T12:00:01+00:00"

    trace = ExecutionTrace(
        run_id="run_err",
        agent_id="agent_1",
        test_case_id="tc_1",
        started_at=t0,
        completed_at=t1,
        events=[
            RunErrorEvent(timestamp=t0, error="LLM timeout"),
            ToolErrorEvent(timestamp=t1, tool_name="issue_refund", error="Unauthorized"),
        ],
    )
    engine = ObservabilityEngine()
    metrics = engine.analyze(trace)

    assert metrics.llm_error_count == 1
    assert metrics.tool_error_count == 1
    assert metrics.status == RunStatus.FAILED


def test_per_step_latency_and_total_duration():
    t0 = "2026-08-12T12:00:00.000000+00:00"
    t1 = "2026-08-12T12:00:00.300000+00:00"
    t2 = "2026-08-12T12:00:01.000000+00:00"

    trace = ExecutionTrace(
        run_id="run_steps",
        agent_id="agent_1",
        test_case_id="tc_1",
        started_at=t0,
        completed_at=t2,
        events=[
            LLMCallEvent(timestamp=t0, input="In", output="Out"),
            ToolCallEvent(timestamp=t1, tool_name="get_order", arguments={}),
        ],
    )
    engine = ObservabilityEngine()
    metrics = engine.analyze(trace)

    assert metrics.duration_ms == 1000.0
    assert len(metrics.step_metrics) == 2
    assert metrics.step_metrics[0].duration_ms == 300.0


def test_token_aggregation():
    t0 = "2026-08-12T12:00:00+00:00"
    t1 = "2026-08-12T12:00:01+00:00"

    trace = ExecutionTrace(
        run_id="run_tokens",
        agent_id="agent_1",
        test_case_id="tc_1",
        started_at=t0,
        completed_at=t1,
        events=[
            LLMCallEvent(timestamp=t0, input="A", output="B", prompt_tokens=150, completion_tokens=50),
            LLMCallEvent(timestamp=t1, input="C", output="D", prompt_tokens=200, completion_tokens=100),
        ],
    )
    engine = ObservabilityEngine()
    metrics = engine.analyze(trace)

    assert metrics.tokens.input_tokens == 350
    assert metrics.tokens.output_tokens == 150
    assert metrics.tokens.total_tokens == 500
    assert metrics.tokens.status == TokenStatus.MEASURED


def test_missing_token_information():
    t0 = "2026-08-12T12:00:00+00:00"

    trace = ExecutionTrace(
        run_id="run_no_tok",
        agent_id="agent_1",
        test_case_id="tc_1",
        started_at=t0,
        completed_at=t0,
        events=[
            LLMCallEvent(timestamp=t0, input="A", output="B")
        ],
    )
    engine = ObservabilityEngine()
    metrics = engine.analyze(trace)

    assert metrics.tokens.status == TokenStatus.UNAVAILABLE
    assert metrics.tokens.input_tokens is None
    assert metrics.tokens.total_tokens is None


def test_cost_calculation_with_pricing():
    t0 = "2026-08-12T12:00:00+00:00"

    trace = ExecutionTrace(
        run_id="run_cost",
        agent_id="agent_1",
        test_case_id="tc_1",
        started_at=t0,
        completed_at=t0,
        events=[
            LLMCallEvent(
                timestamp=t0,
                input="A",
                output="B",
                prompt_tokens=1_000_000,
                completion_tokens=500_000,
            )
        ],
    )
    config = AgentConfig(
        id="agent_1",
        name="Test Agent",
        description="Test agent for cost calculation",
        role="Tester",
        goal="Test costs",
        model="llama-3.1-8b-instant",
    )
    engine = ObservabilityEngine()
    metrics = engine.analyze(trace, config=config)

    assert metrics.cost.status == TokenStatus.ESTIMATED
    assert metrics.cost.input_cost == 0.05
    assert metrics.cost.output_cost == 0.04
    assert metrics.cost.total_cost == 0.09


def test_repeated_tool_calls():
    t0 = "2026-08-12T12:00:00+00:00"

    trace = ExecutionTrace(
        run_id="run_repeat",
        agent_id="agent_1",
        test_case_id="tc_1",
        started_at=t0,
        completed_at=t0,
        events=[
            ToolCallEvent(timestamp=t0, tool_name="get_order", arguments={"order_id": "1234"}),
            ToolCallEvent(timestamp=t0, tool_name="get_order", arguments={"order_id": "1234"}),
            ToolCallEvent(timestamp=t0, tool_name="get_order", arguments={"order_id": "1234"}),
        ],
    )
    engine = ObservabilityEngine()
    metrics = engine.analyze(trace)

    assert metrics.tool_call_count == 3
    assert metrics.repeated_tool_call_count == 2