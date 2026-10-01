"""
Example configuration for the e-commerce refund agent from the platform spec.
Demonstrates how a developer defines a new domain without touching core code.
"""
from src.core.config_models import (
    AgentConfig,
    ToolSchema,
    ToolParameter,
    Permissions,
    Policy,
    PolicyType,
)

ecommerce_refund_agent = AgentConfig(
    name="ecommerce_refund_agent",
    description="Handles customer refund requests for an e-commerce platform.",
    system_prompt=(
        "You are a customer support agent. You may look up orders, check refund "
        "eligibility, and issue refunds only when eligible. Never issue a refund "
        "without first confirming eligibility."
    ),
    tools=[
        ToolSchema(
            name="get_order",
            description="Retrieve an order by ID.",
            parameters=[ToolParameter(name="order_id", type="integer")],
        ),
        ToolSchema(
            name="check_refund_eligibility",
            description="Check whether an order is eligible for a refund.",
            parameters=[ToolParameter(name="order_id", type="integer")],
        ),
        ToolSchema(
            name="issue_refund",
            description="Issue a refund for an order.",
            parameters=[ToolParameter(name="order_id", type="integer")],
            is_sensitive=True,
        ),
        ToolSchema(
            name="send_email",
            description="Send a confirmation email to the customer.",
            parameters=[
                ToolParameter(name="to", type="string"),
                ToolParameter(name="subject", type="string"),
                ToolParameter(name="body", type="string"),
            ],
        ),
    ],
    permissions=Permissions(
        allowed_tools=["get_order", "check_refund_eligibility", "issue_refund", "send_email"],
        blocked_tools=[],
    ),
    policies=[
        Policy(
            id="verify_order_before_refund",
            description="Order must be retrieved before checking eligibility.",
            type=PolicyType.TOOL_ORDER,
            rule={"before": "check_refund_eligibility", "after": "get_order"},
        ),
        Policy(
            id="refund_only_if_eligible",
            description="issue_refund must not be called unless eligibility check passed.",
            type=PolicyType.PRECONDITION,
            rule={"tool": "issue_refund", "requires_prior_tool_result": {"eligible": True}},
        ),
    ],
)
