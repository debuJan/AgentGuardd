from __future__ import annotations

import ipaddress
import json
import os
import socket
import time
import urllib.parse
from typing import Any, Dict, Optional

import httpx

from src.core.config_models import AgentConfig, TestCase
from src.core.trace import (
    ExecutionTrace,
    FinalResponseEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolResultEvent,
)


class ExternalAgentError(Exception):
    """Raised when an external agent cannot be invoked or its response is invalid."""


MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MiB cap on external agent responses
MAX_TOOL_CALLS = 500  # cap on tool calls accepted from one external response


def _private_endpoints_allowed() -> bool:
    """Operator opt-in for non-public external endpoints (dev/test only)."""
    return os.environ.get("AGENTGUARD_ALLOW_PRIVATE_ENDPOINTS", "").lower() in (
        "1", "true", "yes",
    )


def _assert_endpoint_allowed(url: str) -> None:
    """SSRF guard: refuse non-public destinations unless the operator opts in.

    Resolves the endpoint host and rejects loopback, private, link-local,
    multicast, and other non-global addresses (including cloud metadata
    endpoints such as 169.254.169.254). DNS is resolved at request time;
    DNS-rebinding between check and request is a documented limitation.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ExternalAgentError("External endpoint must use http or https.")
    if parsed.username or parsed.password:
        raise ExternalAgentError(
            "External endpoint must not embed credentials in the URL."
        )
    host = parsed.hostname
    if not host:
        raise ExternalAgentError("External endpoint URL has no host.")
    if _private_endpoints_allowed():
        return
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443)
    except socket.gaierror as exc:
        raise ExternalAgentError(
            f"External endpoint host {host!r} could not be resolved."
        ) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ExternalAgentError(
                f"External endpoint {host!r} resolves to a non-public address "
                f"({ip}); refused. Set AGENTGUARD_ALLOW_PRIVATE_ENDPOINTS=1 "
                "to allow private endpoints."
            )


class ExternalAgentAdapter:
    """Invokes an external HTTP agent and normalizes its response into ExecutionTrace."""

    def __init__(self, agent_config: AgentConfig):
        self.agent_config = agent_config

    def invoke(
        self,
        test_case: TestCase,
        run_id: Optional[str] = None,
    ) -> ExecutionTrace:
        if not self.agent_config.endpoint_url:
            trace = ExecutionTrace(
                run_id=run_id or ExecutionTrace.model_fields["run_id"].default_factory(),
                agent_id=self.agent_config.name,
                test_case_id=test_case.id,
            )
            trace.mark_failed(
                f"External agent '{self.agent_config.name}' is missing endpoint_url."
            )
            return trace

        if self.agent_config.adapter_type != "http":
            raise ExternalAgentError(
                f"Unsupported external adapter type: "
                f"{self.agent_config.adapter_type}"
            )

        trace = ExecutionTrace(
            run_id=run_id or ExecutionTrace.model_fields["run_id"].default_factory(),
            agent_id=self.agent_config.name,
            test_case_id=test_case.id,
        )

        headers = {
            "Content-Type": "application/json",
        }

        # Authentication is supplied through an environment variable.
        if self.agent_config.auth_header_env:
            token = os.getenv(self.agent_config.auth_header_env)

            if token:
                headers["Authorization"] = f"Bearer {token}"

        payload = {
            "run_id": trace.run_id,
            "agent_id": self.agent_config.name,
            "test_case_id": test_case.id,
            "input": test_case.user_input,
        }

        start = time.perf_counter()

        try:
            _assert_endpoint_allowed(self.agent_config.endpoint_url)
            with httpx.Client(
                timeout=self.agent_config.timeout_seconds,
                # Ignore ambient proxy env vars: endpoint allowlisting already
                # controls where requests may go, and a malformed proxy env
                # (e.g. an unparseable no_proxy entry) must not break every
                # external-agent invocation at Client construction time.
                trust_env=False,
            ) as client:
                # Stream the body so a malicious oversized response cannot
                # blow up memory before we enforce the size cap.
                with client.stream(
                    "POST",
                    self.agent_config.endpoint_url,
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    raw = self._read_capped(response)

            try:
                data = json.loads(raw)
            except ValueError as exc:
                raise ExternalAgentError(
                    "External agent returned invalid JSON."
                ) from exc

        except httpx.TimeoutException as exc:
            trace.mark_failed(
                f"External agent request timed out after "
                f"{self.agent_config.timeout_seconds} seconds."
            )
            return trace

        except httpx.HTTPStatusError as exc:
            trace.mark_failed(
                f"External agent returned HTTP {exc.response.status_code}."
            )
            return trace

        except httpx.RequestError as exc:
            trace.mark_failed(
                f"External agent request failed: {exc.__class__.__name__}."
            )
            return trace

        except ExternalAgentError as exc:
            trace.mark_failed(str(exc))
            return trace

        except Exception:
            # Do not expose potentially sensitive exception details.
            trace.mark_failed("Unexpected external agent integration failure.")
            return trace

        if not isinstance(data, dict):
            trace.mark_failed(
                "External agent response must be a JSON object."
            )
            return trace

        self._normalize_response(trace, data)

        if trace.error is None:
            trace.mark_complete(final_response=trace.final_response)

        return trace

    @staticmethod
    def _read_capped(response: httpx.Response) -> bytes:
        """Read a streamed response body, enforcing MAX_RESPONSE_BYTES."""
        chunks = []
        total = 0
        for chunk in response.iter_bytes(chunk_size=65536):
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ExternalAgentError(
                    f"External agent response exceeded the "
                    f"{MAX_RESPONSE_BYTES}-byte limit."
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def _normalize_response(
        self,
        trace: ExecutionTrace,
        data: Dict[str, Any],
    ) -> None:
        """Convert the external response into AgentGuard's trace format."""

        status = str(data.get("status", "success")).lower()

        # Normalize tool calls.
        tool_calls = data.get("tool_calls", [])

        if tool_calls is None:
            tool_calls = []

        if not isinstance(tool_calls, list):
            trace.mark_failed("External agent 'tool_calls' must be a list.")
            return

        if len(tool_calls) > MAX_TOOL_CALLS:
            trace.mark_failed(
                f"External agent returned {len(tool_calls)} tool calls "
                f"(limit: {MAX_TOOL_CALLS})."
            )
            return

        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                trace.mark_failed(
                    "Each external tool call must be a JSON object."
                )
                return

            tool_name = tool_call.get("tool_name")

            if not isinstance(tool_name, str) or not tool_name:
                trace.mark_failed(
                    "External tool call is missing a valid tool_name."
                )
                return

            arguments = tool_call.get("arguments", {})

            if not isinstance(arguments, dict):
                trace.mark_failed(
                    f"Arguments for tool '{tool_name}' must be an object."
                )
                return

            trace.add_event(
                ToolCallEvent(
                    tool_name=tool_name,
                    arguments=arguments,
                )
            )

            if "error" in tool_call:
                trace.add_event(
                    ToolErrorEvent(
                        tool_name=tool_name,
                        error=str(tool_call["error"]),
                    )
                )
            else:
                trace.add_event(
                    ToolResultEvent(
                        tool_name=tool_name,
                        result=tool_call.get("result"),
                    )
                )

        # Normalize final response.
        output = data.get("output", "")

        if output is None:
            output = ""

        if not isinstance(output, str):
            output = str(output)

        trace.add_event(
            FinalResponseEvent(content=output)
        )

        trace.final_response = output

        if status in {"failed", "failure", "error"}:
            trace.mark_failed(
                str(data.get("error", "External agent reported failure."))
            )