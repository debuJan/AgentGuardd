import pytest
from pydantic import ValidationError

from src.core.config_models import (
    AgentConfig,
    ToolSchema,
    ToolParameter,
    Permissions,
    Policy,
    PolicyType,
    TestCase,
    TestCaseCategory,
    ExpectedToolCall,
)
from configs.ecommerce_refund_agent import ecommerce_refund_agent


def test_example_config_loads():
    agent = ecommerce_refund_agent
    assert agent.name == "ecommerce_refund_agent"
    assert "get_order" in agent.tool_names()
    assert len(agent.policies) == 2


def test_tool_name_must_be_identifier():
    with pytest.raises(ValidationError):
        ToolSchema(name="bad-name!", description="x")


def test_duplicate_tool_names_rejected():
    with pytest.raises(ValidationError):
        AgentConfig(
            name="dup_agent",
            description="x",
            tools=[
                ToolSchema(name="foo", description="a"),
                ToolSchema(name="foo", description="b"),
            ],
        )


def test_allowed_and_blocked_cannot_overlap():
    with pytest.raises(ValidationError):
        Permissions(allowed_tools=["foo"], blocked_tools=["foo"])


def test_test_case_minimal():
    tc = TestCase(
        id="tc_valid_refund",
        agent_name="ecommerce_refund_agent",
        category=TestCaseCategory.FUNCTIONAL,
        user_input="Refund order #1234.",
        expected_tool_calls=[
            ExpectedToolCall(tool="get_order", arguments={"order_id": 1234}, order=1),
            ExpectedToolCall(tool="check_refund_eligibility", arguments={"order_id": 1234}, order=2),
            ExpectedToolCall(tool="issue_refund", arguments={"order_id": 1234}, order=3),
        ],
        expected_outcome="Refund successful",
        max_tool_calls=5,
    )
    assert tc.category == TestCaseCategory.FUNCTIONAL
    assert len(tc.expected_tool_calls) == 3


def test_policy_types():
    p = Policy(
        id="p1",
        description="order first",
        type=PolicyType.TOOL_ORDER,
        rule={"before": "check_refund_eligibility", "after": "get_order"},
    )
    assert p.type == PolicyType.TOOL_ORDER
