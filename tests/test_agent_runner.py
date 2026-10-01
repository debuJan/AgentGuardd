"""
Agent Runner tests using lightweight stub AgentConfig/TestCase/LLMProvider
objects, so this test suite does not depend on your exact Phase 1
pydantic model field names. Once merged, feel free to add a second suite
that exercises the runner against your real `AgentConfig`/`TestCase`.
"""
from types import SimpleNamespace

import pytest

from src.core.agent_runner import AgentRunner, AgentRunnerError
from src.tools.mock_tools import _reset_state


@pytest.fixture(autouse=True)
def reset_mock_state():
    _reset_state()
    yield
    _reset_state()


def _make_tool(name, description="", parameters=None):
    return SimpleNamespace(name=name, description=description, parameters=parameters or {})


def _make_agent_config():
    return SimpleNamespace(
        name="ecommerce_refund_agent",
        system_prompt="You are a refund agent.",
        tools=[
            _make_tool("get_order"),
            _make_tool("check_refund_eligibility"),
            _make_tool("issue_refund"),
        ],
        allowed_tools=["get_order", "check_refund_eligibility", "issue_refund"],
        blocked_tools=[],
    )


def _make_test_case():
    return SimpleNamespace(id="tc_refund_happy_path", user_input="Refund order #1234.")


class StubLLMProvider:
    """
    Scripted provider: first call requests get_order + check_refund_eligibility,
    second call requests issue_refund, third call returns the final answer.
    """

    def __init__(self):
        self.call_count = 0

    def chat(self, messages, tools):
        self.call_count += 1
        if self.call_count == 1:
            return SimpleNamespace(
                content=None,
                tool_calls=[{"name": "get_order", "arguments": {"order_id": 1234}}],
                prompt_tokens=10,
                completion_tokens=5,
            )
        if self.call_count == 2:
            return SimpleNamespace(
                content=None,
                tool_calls=[{"name": "check_refund_eligibility", "arguments": {"order_id": 1234}}],
                prompt_tokens=10,
                completion_tokens=5,
            )
        if self.call_count == 3:
            return SimpleNamespace(
                content=None,
                tool_calls=[{"name": "issue_refund", "arguments": {"order_id": 1234}}],
                prompt_tokens=10,
                completion_tokens=5,
            )
        return SimpleNamespace(
            content="Your order #1234 has been refunded successfully.",
            tool_calls=[],
            prompt_tokens=10,
            completion_tokens=8,
        )


class LoopingLLMProvider:
    """Always requests a tool call, never produces a final answer."""

    def chat(self, messages, tools):
        return SimpleNamespace(
            content=None,
            tool_calls=[{"name": "get_order", "arguments": {"order_id": 1234}}],
            prompt_tokens=1,
            completion_tokens=1,
        )


def test_full_refund_happy_path_produces_complete_trace():
    runner = AgentRunner(agent_config=_make_agent_config(), llm_provider=StubLLMProvider())
    trace = runner.run(_make_test_case())

    assert trace.error is None
    assert trace.completed_at is not None
    assert trace.tool_call_names() == ["get_order", "check_refund_eligibility", "issue_refund"]
    assert trace.final_response is not None
    assert "refunded" in trace.final_response.lower()


def test_blocked_tool_is_not_executed():
    config = _make_agent_config()
    config.allowed_tools = ["get_order"]  # issue_refund not allowed

    class BlockedToolProvider:
        def __init__(self):
            self.call_count = 0

        def chat(self, messages, tools):
            self.call_count += 1
            if self.call_count == 1:
                return SimpleNamespace(
                    content=None,
                    tool_calls=[{"name": "issue_refund", "arguments": {"order_id": 1234}}],
                    prompt_tokens=1,
                    completion_tokens=1,
                )
            return SimpleNamespace(content="Done.", tool_calls=[], prompt_tokens=1, completion_tokens=1)

    runner = AgentRunner(agent_config=config, llm_provider=BlockedToolProvider())
    trace = runner.run(_make_test_case())

    # The tool call was attempted and recorded, but resulted in a ToolErrorEvent
    tool_error_events = [e for e in trace.events if e.type == "tool_error"]
    assert len(tool_error_events) == 1
    assert "not permitted" in tool_error_events[0].error


def test_infinite_tool_loop_is_capped_and_marks_trace_failed():
    runner = AgentRunner(agent_config=_make_agent_config(), llm_provider=LoopingLLMProvider())
    trace = runner.run(_make_test_case())

    assert trace.error is not None
    assert "max turns" in trace.error.lower()


class _RefundOnlyProvider:
    """Requests issue_refund(order 1234) once, then answers. Fresh instance per run."""

    def __init__(self):
        self.call_count = 0

    def chat(self, messages, tools):
        self.call_count += 1
        if self.call_count == 1:
            return SimpleNamespace(
                content=None,
                tool_calls=[{"name": "issue_refund", "arguments": {"order_id": 1234}}],
                prompt_tokens=1,
                completion_tokens=1,
            )
        return SimpleNamespace(
            content="Refunded.",
            tool_calls=[],
            prompt_tokens=1,
            completion_tokens=1,
        )


def test_sequential_runs_do_not_leak_mock_tool_state():
    """Regression: module-global mock state (e.g. issued refunds) must not
    leak across runs in the same process (sequential POST /runs)."""
    from src.core.trace import ToolErrorEvent, ToolResultEvent

    runner = AgentRunner(agent_config=_make_agent_config(), llm_provider=_RefundOnlyProvider())

    first = runner.run(_make_test_case())
    runner.llm_provider = _RefundOnlyProvider()  # fresh script per run
    second = runner.run(_make_test_case())

    for trace in (first, second):
        assert trace.error is None
        errors = [e for e in trace.events if isinstance(e, ToolErrorEvent)]
        assert not errors, f"run leaked state into a ToolErrorEvent: {errors}"
        refunds = [
            e for e in trace.events
            if isinstance(e, ToolResultEvent) and e.tool_name == "issue_refund"
        ]
        assert refunds and refunds[0].result["status"] == "success"
