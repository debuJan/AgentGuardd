from types import SimpleNamespace

import pytest

from src.core.trace import (
    ExecutionTrace,
    FinalResponseEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolResultEvent,
)
from src.evaluation.engine import EvaluationEngine


def _tool(name, description="", parameters=None):
    return SimpleNamespace(name=name, description=description, parameters=parameters or {})


def _policy(name, before_tool, after_tool):
    return SimpleNamespace(name=name, before_tool=before_tool, after_tool=after_tool)


def _agent_config(allowed=None, blocked=None, policies=None):
    return SimpleNamespace(
        name="ecommerce_refund_agent",
        system_prompt="You are a refund agent.",
        tools=[_tool("get_order"), _tool("check_refund_eligibility"), _tool("issue_refund")],
        allowed_tools=allowed if allowed is not None else ["get_order", "check_refund_eligibility", "issue_refund"],
        blocked_tools=blocked if blocked is not None else [],
        policies=policies if policies is not None else [_policy("verify_before_refund", "get_order", "issue_refund")],
    )


def _test_case(**overrides):
    defaults = dict(
        id="tc_refund_happy_path",
        user_input="Refund order #1234.",
        expected_tool_calls=[
            SimpleNamespace(
                tool="get_order",
                arguments={"order_id": 1234},
                order=1,
            ),
            SimpleNamespace(
                tool="check_refund_eligibility",
                arguments={"order_id": 1234},
                order=2,
            ),
            SimpleNamespace(
                tool="issue_refund",
                arguments={"order_id": 1234},
                order=3,
            ),
        ],
        expected_outcome="success",
        max_tool_calls=None,
        max_latency_ms=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _trace_with_events(*events, final_response=None, error=None):
    trace = ExecutionTrace(agent_id="ecommerce_refund_agent", test_case_id="tc_refund_happy_path")
    for e in events:
        trace.add_event(e)
    if final_response is not None:
        trace.add_event(FinalResponseEvent(content=final_response))
        trace.mark_complete(final_response=final_response)
    if error is not None:
        trace.mark_failed(error)
    return trace


def _happy_path_trace():
    return _trace_with_events(
        ToolCallEvent(tool_name="get_order", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="get_order", result={"order_id": 1234, "status": "delivered"}),
        ToolCallEvent(tool_name="check_refund_eligibility", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="check_refund_eligibility", result={"eligible": True}),
        ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="issue_refund", result={"status": "success"}),
        final_response="Your order #1234 has been refunded successfully.",
    )


def test_perfect_refund_trace_passes_with_full_score():
    engine = EvaluationEngine()
    result = engine.evaluate(_happy_path_trace(), _agent_config(), _test_case())

    assert result.passed is True
    assert result.reliability_score == 100.0
    assert result.failures == []


def test_missing_expected_tool_fails():
    trace = _trace_with_events(
        ToolCallEvent(tool_name="get_order", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="get_order", result={"status": "delivered"}),
        ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="issue_refund", result={"status": "success"}),
        final_response="Refunded successfully.",
    )
    engine = EvaluationEngine()
    result = engine.evaluate(trace, _agent_config(), _test_case())

    assert result.passed is False
    check = result.get_check("tool_selection")
    assert check.passed is False
    assert "check_refund_eligibility" in check.message


def test_wrong_tool_argument_fails():
    trace = _trace_with_events(
        ToolCallEvent(tool_name="get_order", arguments={"order_id": 1235}),
        ToolResultEvent(tool_name="get_order", result={"status": "delivered"}),
        ToolCallEvent(tool_name="check_refund_eligibility", arguments={"order_id": 1235}),
        ToolResultEvent(tool_name="check_refund_eligibility", result={"eligible": True}),
        ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1235}),
        ToolResultEvent(tool_name="issue_refund", result={"status": "success"}),
        final_response="Refunded successfully.",
    )
    engine = EvaluationEngine()
    result = engine.evaluate(trace, _agent_config(), _test_case())

    check = result.get_check("tool_arguments")
    assert check.passed is False
    assert result.passed is False


def test_wrong_sequence_fails():
    trace = _trace_with_events(
        ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="issue_refund", result={"status": "success"}),
        ToolCallEvent(tool_name="get_order", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="get_order", result={"status": "delivered"}),
        ToolCallEvent(tool_name="check_refund_eligibility", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="check_refund_eligibility", result={"eligible": True}),
        final_response="Refunded successfully.",
    )
    engine = EvaluationEngine()
    result = engine.evaluate(trace, _agent_config(), _test_case())

    check = result.get_check("tool_sequence")
    assert check.passed is False
    assert result.passed is False


def test_unauthorized_tool_usage_is_hard_gated_to_fail():
    trace = _trace_with_events(
        ToolCallEvent(tool_name="send_email", arguments={"to": "x@example.com"}),
        ToolResultEvent(tool_name="send_email", result={"status": "sent"}),
        final_response="Email sent.",
    )
    config = _agent_config(allowed=["get_order", "check_refund_eligibility", "issue_refund"])
    engine = EvaluationEngine()
    result = engine.evaluate(trace, config, _test_case(expected_tools=[], expected_tool_sequence=[], expected_tool_arguments={}, expected_success=None))

    check = result.get_check("unauthorized_tool_usage")
    assert check.passed is False
    assert result.passed is False
    assert result.reliability_score == 0.0


def test_blocked_tool_usage_is_hard_gated_to_fail():
    trace = _trace_with_events(
        ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="issue_refund", result={"status": "success"}),
        final_response="Refunded.",
    )
    config = _agent_config(blocked=["issue_refund"])
    engine = EvaluationEngine()
    result = engine.evaluate(trace, config, _test_case(expected_tools=[], expected_tool_sequence=[], expected_tool_arguments={}, expected_success=None))

    check = result.get_check("blocked_tool_usage")
    assert check.passed is False
    assert result.passed is False
    assert result.reliability_score == 0.0


def test_tool_failure_is_detected():
    trace = _trace_with_events(
        ToolCallEvent(tool_name="get_order", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="get_order", result={"status": "delivered"}),
        ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1234}),
        ToolErrorEvent(tool_name="issue_refund", error="Order not eligible for refund"),
        final_response="There was an issue processing your refund.",
    )
    engine = EvaluationEngine()
    result = engine.evaluate(trace, _agent_config(), _test_case(expected_tool_sequence=[]))

    check = result.get_check("tool_errors")
    assert check.passed is False
    assert result.passed is False


def test_hallucinated_success_fails_outcome_consistency():
    trace = _trace_with_events(
        ToolCallEvent(tool_name="get_order", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="get_order", result={"status": "delivered"}),
        ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="issue_refund", result={"status": "failed"}),
        final_response="Your refund has been successfully processed.",
    )
    engine = EvaluationEngine()
    result = engine.evaluate(trace, _agent_config(), _test_case(expected_tool_sequence=[], expected_success=None))

    check = result.get_check("outcome_consistency")
    assert check.passed is False
    assert "issue_refund" in check.message
    assert result.passed is False


def test_policy_violation_fails_when_order_is_wrong():
    trace = _trace_with_events(
        ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="issue_refund", result={"status": "success"}),
        ToolCallEvent(tool_name="get_order", arguments={"order_id": 1234}),
        ToolResultEvent(tool_name="get_order", result={"status": "delivered"}),
        final_response="Refunded.",
    )
    engine = EvaluationEngine()
    result = engine.evaluate(trace, _agent_config(), _test_case(expected_tools=[], expected_tool_sequence=[], expected_tool_arguments={}, expected_success=None))

    check = result.get_check("policy_compliance")
    assert check.passed is False
    assert "verify_before_refund" in check.message
    assert result.passed is False


def test_score_calculation_is_deterministic_and_weighted():
    engine = EvaluationEngine()
    result = engine.evaluate(_happy_path_trace(), _agent_config(), _test_case())

    # every weighted check passed at score 1.0 => total should be exactly 100
    total_weight = sum(c.weight for c in result.checks)
    assert total_weight == pytest.approx(1.0, abs=0.01)
    assert result.reliability_score == 100.0

    # run it twice, should be perfectly reproducible
    result2 = engine.evaluate(_happy_path_trace(), _agent_config(), _test_case())
    assert result2.reliability_score == result.reliability_score

def test_empty_trace_fails_reliability():
    engine = EvaluationEngine()

    result = engine.evaluate(
        _trace_with_events(),
        _agent_config(),
        _test_case(),
    )

    assert result.passed is False
    assert result.reliability_score < 100.0
    assert len(result.failures) > 0


def test_extra_unexpected_tool_fails_reliability():
    trace = _trace_with_events(
        ToolCallEvent(
            tool_name="get_order",
            arguments={"order_id": 1234},
        ),
        ToolResultEvent(
            tool_name="get_order",
            result={"status": "delivered"},
        ),
        ToolCallEvent(
            tool_name="check_refund_eligibility",
            arguments={"order_id": 1234},
        ),
        ToolResultEvent(
            tool_name="check_refund_eligibility",
            result={"eligible": True},
        ),
        ToolCallEvent(
            tool_name="issue_refund",
            arguments={"order_id": 1234},
        ),
        ToolResultEvent(
            tool_name="issue_refund",
            result={"status": "success"},
        ),
        ToolCallEvent(
            tool_name="unexpected_tool",
            arguments={},
        ),
        ToolResultEvent(
            tool_name="unexpected_tool",
            result={"status": "success"},
        ),
        final_response="Refunded.",
    )

    result = EvaluationEngine().evaluate(
        trace,
        _agent_config(),
        _test_case(),
    )

    assert result.passed is False


def test_wrong_tool_sequence_fails_reliability():
    trace = _trace_with_events(
        ToolCallEvent(
            tool_name="get_order",
            arguments={"order_id": 1234},
        ),
        ToolResultEvent(
            tool_name="get_order",
            result={"status": "delivered"},
        ),
        ToolCallEvent(
            tool_name="issue_refund",
            arguments={"order_id": 1234},
        ),
        ToolResultEvent(
            tool_name="issue_refund",
            result={"status": "success"},
        ),
        ToolCallEvent(
            tool_name="check_refund_eligibility",
            arguments={"order_id": 1234},
        ),
        ToolResultEvent(
            tool_name="check_refund_eligibility",
            result={"eligible": True},
        ),
        final_response="Refunded.",
    )

    result = EvaluationEngine().evaluate(
        trace,
        _agent_config(),
        _test_case(),
    )

    check = result.get_check("tool_sequence")

    assert check.passed is False
    assert result.passed is False

def test_duplicate_tool_call_fails_reliability():
        trace = _trace_with_events(
            ToolCallEvent(tool_name="get_order", arguments={"order_id": 1234}),
            ToolResultEvent(tool_name="get_order", result={"status": "delivered"}),

            # Duplicate call
            ToolCallEvent(tool_name="get_order", arguments={"order_id": 1234}),
            ToolResultEvent(tool_name="get_order", result={"status": "delivered"}),

            ToolCallEvent(
                tool_name="check_refund_eligibility",
                arguments={"order_id": 1234},
            ),
            ToolResultEvent(
                tool_name="check_refund_eligibility",
                result={"eligible": True},
            ),

            ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1234}),
            ToolResultEvent(tool_name="issue_refund", result={"status": "success"}),

            final_response="Refunded.",
        )

        result = EvaluationEngine().evaluate(
            trace,
            _agent_config(),
            _test_case(),
        )

        assert result.passed is False

def test_repeated_tool_call_with_wrong_argument_fails():
        trace = _trace_with_events(
            ToolCallEvent(tool_name="get_order", arguments={"order_id": 1234}),
            ToolResultEvent(tool_name="get_order", result={"status": "delivered"}),

            # Second call uses the wrong order ID
            ToolCallEvent(tool_name="get_order", arguments={"order_id": 9999}),
            ToolResultEvent(tool_name="get_order", result={"status": "delivered"}),

            ToolCallEvent(
                tool_name="check_refund_eligibility",
                arguments={"order_id": 1234},
            ),
            ToolResultEvent(
                tool_name="check_refund_eligibility",
                result={"eligible": True},
            ),

            ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1234}),
            ToolResultEvent(tool_name="issue_refund", result={"status": "success"}),

            final_response="Refunded.",
        )

        result = EvaluationEngine().evaluate(
            trace,
            _agent_config(),
            _test_case(),
        )

        assert result.passed is False