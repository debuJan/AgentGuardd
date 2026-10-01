import pytest

from src.tools.mock_tools import MockToolError, MockToolRegistry, _reset_state


@pytest.fixture(autouse=True)
def reset_mock_state():
    _reset_state()
    yield
    _reset_state()


def test_get_order_success():
    registry = MockToolRegistry()
    result = registry.call("get_order", {"order_id": 1234})
    assert result["order_id"] == 1234
    assert result["status"] == "delivered"


def test_get_order_not_found():
    registry = MockToolRegistry()
    with pytest.raises(MockToolError):
        registry.call("get_order", {"order_id": 424242})


def test_refund_eligibility_true_for_delivered_order():
    registry = MockToolRegistry()
    result = registry.call("check_refund_eligibility", {"order_id": 1234})
    assert result["eligible"] is True


def test_refund_eligibility_false_for_already_refunded_order():
    registry = MockToolRegistry()
    result = registry.call("check_refund_eligibility", {"order_id": 9999})
    assert result["eligible"] is False


def test_issue_refund_success():
    registry = MockToolRegistry()
    result = registry.call("issue_refund", {"order_id": 1234})
    assert result["status"] == "success"


def test_issue_refund_blocked_when_not_eligible():
    registry = MockToolRegistry()
    with pytest.raises(MockToolError):
        registry.call("issue_refund", {"order_id": 9999})


def test_registry_restricts_to_allowed_tools():
    registry = MockToolRegistry(allowed_tool_names=["get_order"])
    assert registry.has_tool("get_order") is True
    assert registry.has_tool("issue_refund") is False
    with pytest.raises(MockToolError):
        registry.call("issue_refund", {"order_id": 1234})


def test_registry_rejects_unknown_tool_name():
    with pytest.raises(MockToolError):
        MockToolRegistry(allowed_tool_names=["not_a_real_tool"])
