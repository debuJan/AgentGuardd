"""
Shared pytest fixtures for the reporting tests (and reusable elsewhere).

Built against the real models in src/core/config_models.py and
src/core/trace.py.
"""
import pytest

from src.core.config_models import (
    AgentConfig,
    ExpectedToolCall,
    Permissions,
    Policy,
    PolicyType,
    TestCase,
    TestCaseCategory,
    ToolParameter,
    ToolSchema,
)
from src.core.trace import (
    ExecutionTrace,
    FinalResponseEvent,
    LLMCallEvent,
    ToolCallEvent,
    ToolResultEvent,
)


@pytest.fixture
def agent_config() -> AgentConfig:
    return AgentConfig(
        name="ecommerce_refund_agent",
        description="Handles order refund requests.",
        system_prompt="You are a refund agent. Verify orders before issuing refunds.",
        tools=[
            ToolSchema(
                name="get_order",
                description="Look up an order by id.",
                parameters=[ToolParameter(name="order_id", type="integer")],
            ),
            ToolSchema(
                name="check_refund_eligibility",
                description="Check whether an order is eligible for refund.",
                parameters=[ToolParameter(name="order_id", type="integer")],
            ),
            ToolSchema(
                name="issue_refund",
                description="Issue a refund for an order.",
                parameters=[ToolParameter(name="order_id", type="integer")],
                is_sensitive=True,
            ),
        ],
        permissions=Permissions(
            allowed_tools=["get_order", "check_refund_eligibility", "issue_refund"],
            blocked_tools=[],
        ),
        policies=[
            Policy(
                id="verify_before_refund",
                description="Must check refund eligibility before issuing a refund.",
                type=PolicyType.TOOL_ORDER,
                rule={"before": "check_refund_eligibility", "after": "issue_refund"},
            )
        ],
    )


@pytest.fixture
def test_case() -> TestCase:
    return TestCase(
        id="tc_refund_happy_path",
        agent_name="ecommerce_refund_agent",
        category=TestCaseCategory.FUNCTIONAL,
        user_input="Refund order #1234.",
        expected_tool_calls=[
            ExpectedToolCall(tool="get_order", order=1),
            ExpectedToolCall(tool="check_refund_eligibility", order=2),
            ExpectedToolCall(tool="issue_refund", order=3),
        ],
        expected_outcome="order #1234 has been refunded successfully",
    )


@pytest.fixture
def clean_trace() -> ExecutionTrace:
    trace = ExecutionTrace(
        run_id="run_clean_001",
        agent_id="ecommerce_refund_agent",
        test_case_id="tc_refund_happy_path",
    )

    trace.add_event(LLMCallEvent(
        input="Refund order #1234.",
        output=None,
        tool_calls_requested=["get_order"],
        prompt_tokens=120,
        completion_tokens=18,
    ))
    trace.add_event(ToolCallEvent(tool_name="get_order", arguments={"order_id": 1234}))
    trace.add_event(ToolResultEvent(
        tool_name="get_order",
        result={"order_id": 1234, "status": "delivered", "amount": 59.99},
    ))

    trace.add_event(LLMCallEvent(
        input="(tool result: get_order)",
        output=None,
        tool_calls_requested=["check_refund_eligibility"],
        prompt_tokens=140,
        completion_tokens=15,
    ))
    trace.add_event(ToolCallEvent(tool_name="check_refund_eligibility", arguments={"order_id": 1234}))
    trace.add_event(ToolResultEvent(
        tool_name="check_refund_eligibility",
        result={"order_id": 1234, "eligible": True, "reason": "Order delivered and within refund window"},
    ))

    trace.add_event(LLMCallEvent(
        input="(tool result: check_refund_eligibility)",
        output=None,
        tool_calls_requested=["issue_refund"],
        prompt_tokens=150,
        completion_tokens=12,
    ))
    trace.add_event(ToolCallEvent(tool_name="issue_refund", arguments={"order_id": 1234}))
    trace.add_event(ToolResultEvent(
        tool_name="issue_refund",
        result={"order_id": 1234, "amount": 59.99, "status": "success"},
    ))

    trace.add_event(LLMCallEvent(
        input="(tool result: issue_refund)",
        output="Your order #1234 has been refunded successfully.",
        tool_calls_requested=[],
        prompt_tokens=160,
        completion_tokens=20,
    ))
    trace.add_event(FinalResponseEvent(content="Your order #1234 has been refunded successfully."))

    trace.mark_complete(final_response="Your order #1234 has been refunded successfully.")
    return trace