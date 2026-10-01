"""
Mock Tool Layer.

Deterministic, in-memory tools used for agent evaluation runs.
No real destructive or financial side effects.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict

logger = logging.getLogger(__name__)


class MockToolError(Exception):
    """Raised when a mock tool is called with invalid arguments or state."""


# ---------------------------------------------------------------------------
# In-memory fixture data
# ---------------------------------------------------------------------------

_ORDERS: Dict[int, Dict[str, Any]] = {
    1234: {"order_id": 1234, "status": "delivered", "amount": 59.99, "customer_email": "jane@example.com"},
    5678: {"order_id": 5678, "status": "pending", "amount": 120.00, "customer_email": "bob@example.com"},
    9999: {"order_id": 9999, "status": "refunded", "amount": 15.50, "customer_email": "amy@example.com"},
}

_REFUNDS_ISSUED: Dict[int, Dict[str, Any]] = {}


def _reset_state() -> None:
    """Reset mutable mock state. Intended for use between test runs."""
    _REFUNDS_ISSUED.clear()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_order(order_id: int) -> Dict[str, Any]:
    order = _ORDERS.get(order_id)
    if order is None:
        raise MockToolError(f"Order {order_id} not found")
    logger.debug("get_order(%s) -> %s", order_id, order)
    return dict(order)


def check_refund_eligibility(order_id: int) -> Dict[str, Any]:
    order = _ORDERS.get(order_id)
    if order is None:
        raise MockToolError(f"Order {order_id} not found")

    if order_id in _REFUNDS_ISSUED:
        eligible = False
        reason = "Refund already issued"
    elif order["status"] == "delivered":
        eligible = True
        reason = "Order delivered and within refund window"
    elif order["status"] == "refunded":
        eligible = False
        reason = "Order already refunded"
    else:
        eligible = False
        reason = f"Order status '{order['status']}' is not eligible"

    result = {"order_id": order_id, "eligible": eligible, "reason": reason}
    logger.debug("check_refund_eligibility(%s) -> %s", order_id, result)
    return result


def issue_refund(order_id: int) -> Dict[str, Any]:
    order = _ORDERS.get(order_id)
    if order is None:
        raise MockToolError(f"Order {order_id} not found")

    eligibility = check_refund_eligibility(order_id)
    if not eligibility["eligible"]:
        raise MockToolError(f"Order {order_id} is not eligible for refund: {eligibility['reason']}")

    refund_record = {
        "order_id": order_id,
        "amount": order["amount"],
        "status": "success",
    }
    _REFUNDS_ISSUED[order_id] = refund_record
    logger.debug("issue_refund(%s) -> %s", order_id, refund_record)
    return dict(refund_record)


def send_email(to: str, subject: str, body: str) -> Dict[str, Any]:
    result = {"to": to, "subject": subject, "status": "sent"}
    logger.debug("send_email(%s, %s) -> %s", to, subject, result)
    return result


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class MockToolRegistry:
    """
    Maps tool names (as declared in AgentConfig.tools) to callables.

    The AgentRunner uses this registry to execute tool calls requested
    by the LLM, restricted to the agent's allowed_tools.
    """

    _ALL_TOOLS: Dict[str, Callable[..., Dict[str, Any]]] = {
        "get_order": get_order,
        "check_refund_eligibility": check_refund_eligibility,
        "issue_refund": issue_refund,
        "send_email": send_email,
    }

    def __init__(self, allowed_tool_names: list[str] | None = None):
        """
        If allowed_tool_names is provided, only those tools are registered.
        Otherwise all known mock tools are available (runner still enforces
        AgentConfig permissions separately).
        """
        if allowed_tool_names is None:
            self._tools = dict(self._ALL_TOOLS)
        else:
            missing = [n for n in allowed_tool_names if n not in self._ALL_TOOLS]
            if missing:
                raise MockToolError(f"No mock implementation for tools: {missing}")
            self._tools = {n: self._ALL_TOOLS[n] for n in allowed_tool_names}

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.has_tool(name):
            raise MockToolError(f"Tool '{name}' is not registered in this run")
        fn = self._tools[name]
        return fn(**arguments)

    def reset(self) -> None:
        _reset_state()
