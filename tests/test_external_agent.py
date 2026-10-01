import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.core.agent_runner import AgentRunner
from src.core.config_models import AgentConfig, TestCase
from src.core.trace import (
    FinalResponseEvent,
    ToolCallEvent,
    ToolResultEvent,
    RunErrorEvent,
)
from src.integrations.external_agent import (
    ExternalAgentAdapter,
    ExternalAgentError,
    _assert_endpoint_allowed,
)


@pytest.fixture(autouse=True)
def _allow_private_endpoints(monkeypatch):
    # The SSRF guard is tested separately below; the mocked-transport tests
    # below must not depend on real DNS resolution.
    monkeypatch.setenv("AGENTGUARD_ALLOW_PRIVATE_ENDPOINTS", "1")


def make_external_agent():
    return AgentConfig(
        name="External Test Agent",
        description="Test external agent",
        execution_type="external",
        adapter_type="http",
        endpoint_url="https://example.com/agent",
        timeout_seconds=5.0,
    )


def make_test_case():
    return TestCase(
        id="tc_external_001",
        agent_name="External Test Agent",
        user_input="Cancel order 123",
    )


def _stream_cm(payload=None, raw=None, raise_for_status_error=None):
    """Build a mocked httpx.Client.stream(...) context manager."""
    response = MagicMock()
    if raise_for_status_error is not None:
        response.raise_for_status.side_effect = raise_for_status_error
    else:
        response.raise_for_status.return_value = None
    body = raw if raw is not None else json.dumps(payload or {}).encode()
    response.iter_bytes.return_value = [body]

    cm = MagicMock()
    cm.__enter__.return_value = response
    cm.__exit__.return_value = False
    return cm


def test_external_agent_success():
    agent_config = make_external_agent()
    test_case = make_test_case()

    cm = _stream_cm({
        "status": "success",
        "output": "Order cancelled successfully.",
        "tool_calls": [
            {
                "tool_name": "cancel_order",
                "arguments": {"order_id": "123"},
                "result": {"success": True},
            }
        ],
    })

    with patch(
        "src.integrations.external_agent.httpx.Client.stream",
        return_value=cm,
    ) as mock_stream:
        runner = AgentRunner(
            agent_config=agent_config,
            llm_provider=None,
        )

        trace = runner.run(test_case)

    assert mock_stream.called
    assert trace.error is None
    assert trace.final_response == "Order cancelled successfully."

    assert any(
        isinstance(event, ToolCallEvent)
        and event.tool_name == "cancel_order"
        for event in trace.events
    )

    assert any(
        isinstance(event, ToolResultEvent)
        and event.tool_name == "cancel_order"
        for event in trace.events
    )

    assert any(
        isinstance(event, FinalResponseEvent)
        and event.content == "Order cancelled successfully."
        for event in trace.events
    )

    assert trace.completed_at is not None


def test_external_agent_timeout():
    agent_config = make_external_agent()
    test_case = make_test_case()

    with patch(
        "src.integrations.external_agent.httpx.Client.stream",
        side_effect=httpx.TimeoutException("timeout"),
    ):
        runner = AgentRunner(
            agent_config=agent_config,
            llm_provider=None,
        )

        trace = runner.run(test_case)

    assert trace.error is not None
    assert "timed out" in trace.error.lower()

    assert any(
        isinstance(event, RunErrorEvent)
        for event in trace.events
    )


def test_external_agent_http_error():
    agent_config = make_external_agent()
    test_case = make_test_case()

    response = MagicMock()
    response.status_code = 500

    error = httpx.HTTPStatusError(
        "server error",
        request=MagicMock(),
        response=response,
    )

    cm = _stream_cm(raise_for_status_error=error)

    with patch(
        "src.integrations.external_agent.httpx.Client.stream",
        return_value=cm,
    ):
        runner = AgentRunner(
            agent_config=agent_config,
            llm_provider=None,
        )

        trace = runner.run(test_case)

    assert trace.error is not None
    assert "500" in trace.error


def test_external_agent_invalid_json():
    agent_config = make_external_agent()
    test_case = make_test_case()

    cm = _stream_cm(raw=b"this is not json")

    with patch(
        "src.integrations.external_agent.httpx.Client.stream",
        return_value=cm,
    ):
        runner = AgentRunner(
            agent_config=agent_config,
            llm_provider=None,
        )

        trace = runner.run(test_case)

    assert trace.error is not None
    assert "invalid json" in trace.error.lower()


def test_external_agent_requires_endpoint():
    agent_config = AgentConfig(
        name="External Test Agent",
        description="Test external agent",
        execution_type="external",
        adapter_type="http",
        endpoint_url=None,
    )

    test_case = make_test_case()

    runner = AgentRunner(
        agent_config=agent_config,
        llm_provider=None,
    )

    trace = runner.run(test_case)

    assert trace.error is not None
    assert "endpoint_url" in trace.error


def test_external_agent_oversized_response_fails_run():
    agent_config = make_external_agent()
    test_case = make_test_case()

    response = MagicMock()
    response.raise_for_status.return_value = None
    # Chunks that together exceed the 2 MiB cap.
    response.iter_bytes.return_value = [b"x" * (1024 * 1024)] * 3

    cm = MagicMock()
    cm.__enter__.return_value = response
    cm.__exit__.return_value = False

    with patch(
        "src.integrations.external_agent.httpx.Client.stream",
        return_value=cm,
    ):
        trace = ExternalAgentAdapter(agent_config).invoke(test_case)

    assert trace.error is not None
    assert "exceeded" in trace.error.lower()


def test_external_agent_too_many_tool_calls_fails_run():
    agent_config = make_external_agent()
    test_case = make_test_case()

    cm = _stream_cm({
        "status": "success",
        "output": "done",
        "tool_calls": [
            {"tool_name": f"tool_{i}", "arguments": {}} for i in range(501)
        ],
    })

    with patch(
        "src.integrations.external_agent.httpx.Client.stream",
        return_value=cm,
    ):
        trace = ExternalAgentAdapter(agent_config).invoke(test_case)

    assert trace.error is not None
    assert "tool calls" in trace.error.lower()


def test_external_agent_unsupported_adapter_fails_run_not_crash():
    agent_config = make_external_agent()
    # Bypass the AgentConfig validator to simulate a legacy config object.
    object.__setattr__(agent_config, "adapter_type", "grpc")

    runner = AgentRunner(agent_config=agent_config, llm_provider=None)
    trace = runner.run(make_test_case())

    assert trace.error is not None
    assert "adapter" in trace.error.lower()


# ---------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------

def test_ssrf_guard_blocks_loopback_by_default(monkeypatch):
    monkeypatch.delenv("AGENTGUARD_ALLOW_PRIVATE_ENDPOINTS", raising=False)
    with pytest.raises(ExternalAgentError, match="non-public"):
        _assert_endpoint_allowed("http://127.0.0.1:8080/agent")


def test_ssrf_guard_blocks_metadata_endpoint(monkeypatch):
    monkeypatch.delenv("AGENTGUARD_ALLOW_PRIVATE_ENDPOINTS", raising=False)
    with pytest.raises(ExternalAgentError, match="non-public"):
        _assert_endpoint_allowed("http://169.254.169.254/latest/meta-data/")


def test_ssrf_guard_blocks_private_range(monkeypatch):
    monkeypatch.delenv("AGENTGUARD_ALLOW_PRIVATE_ENDPOINTS", raising=False)
    with pytest.raises(ExternalAgentError, match="non-public"):
        _assert_endpoint_allowed("http://10.0.0.5/agent")


def test_ssrf_guard_allows_private_with_operator_opt_in(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_ALLOW_PRIVATE_ENDPOINTS", "1")
    # Must not raise (and must not need DNS for the opt-in path).
    _assert_endpoint_allowed("http://127.0.0.1:8080/agent")


def test_ssrf_guard_rejects_non_http_scheme():
    with pytest.raises(ExternalAgentError, match="http or https"):
        _assert_endpoint_allowed("ftp://example.com/agent")


def test_ssrf_guard_rejects_credentials_in_url():
    with pytest.raises(ExternalAgentError, match="credentials"):
        _assert_endpoint_allowed("https://user:pass@example.com/agent")


def test_ssrf_guard_rejects_unresolvable_host(monkeypatch):
    import socket as _socket

    monkeypatch.delenv("AGENTGUARD_ALLOW_PRIVATE_ENDPOINTS", raising=False)
    monkeypatch.setattr(
        "src.integrations.external_agent.socket.getaddrinfo",
        MagicMock(side_effect=_socket.gaierror("Name or service not known")),
    )
    with pytest.raises(ExternalAgentError, match="could not be resolved"):
        _assert_endpoint_allowed("http://nonexistent.invalid/agent")


# ---------------------------------------------------------------------
# auth_header_env allowlist
# ---------------------------------------------------------------------

def test_auth_header_env_rejected_when_not_allowlisted(monkeypatch):
    monkeypatch.delenv("AGENTGUARD_ALLOWED_AUTH_ENV", raising=False)
    with pytest.raises(Exception, match="not permitted"):
        AgentConfig(
            name="x",
            description="x",
            auth_header_env="DATABASE_URL",
        )


def test_auth_header_env_rejected_with_bad_name(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_ALLOWED_AUTH_ENV", "MY_TOKEN")
    with pytest.raises(Exception, match="valid environment variable name"):
        AgentConfig(
            name="x",
            description="x",
            auth_header_env="../../etc/passwd",
        )


def test_auth_header_env_allowed_when_allowlisted(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_ALLOWED_AUTH_ENV", "MY_AGENT_TOKEN")
    monkeypatch.setenv("MY_AGENT_TOKEN", "secret-token")
    config = AgentConfig(
        name="x",
        description="x",
        auth_header_env="MY_AGENT_TOKEN",
    )
    assert config.auth_header_env == "MY_AGENT_TOKEN"


def test_execution_type_rejects_unknown_value():
    with pytest.raises(Exception, match="Unknown execution_type"):
        AgentConfig(name="x", description="x", execution_type="quantum")


def test_endpoint_url_rejects_non_http_scheme():
    with pytest.raises(Exception, match="http or https"):
        AgentConfig(name="x", description="x", endpoint_url="ftp://example.com/x")
