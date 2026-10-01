"""
Agent Runner.

Loads an AgentConfig + TestCase, drives the configured LLM provider with
the agent's tools available, executes tool calls against the mock tool
layer, and returns a fully populated ExecutionTrace.

For external agents, the runner delegates execution to the configured
ExternalAgentAdapter while preserving the same ExecutionTrace contract.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.core.trace import (
    ExecutionTrace,
    FinalResponseEvent,
    LLMCallEvent,
    ToolCallEvent,
    ToolErrorEvent,
    ToolResultEvent,
)
from src.integrations.external_agent import ExternalAgentAdapter
from src.tools.mock_tools import MockToolError, MockToolRegistry


logger = logging.getLogger(__name__)

MAX_TURNS = 8  # hard cap to prevent infinite tool loops


class AgentRunnerError(Exception):
    """Raised for unrecoverable runner-level failures (not tool errors)."""


class AgentRunner:
    """
    Executes a single TestCase against an AgentConfig.

    Internal agents use the existing live LLM provider + mock tool flow.

    External agents are delegated to ExternalAgentAdapter, which normalizes
    the external execution into the same ExecutionTrace representation.
    """

    def __init__(
        self,
        agent_config: Any,
        llm_provider: Any,
        tool_registry: Optional[MockToolRegistry] = None,
    ):
        self.agent_config = agent_config
        self.llm_provider = llm_provider

        execution_type = getattr(
            self.agent_config,
            "execution_type",
            "internal",
        )

        if execution_type == "external":
            self.tool_registry = tool_registry
        else:
            allowed = self._get_allowed_tool_names()
            self.tool_registry = tool_registry or MockToolRegistry(
                allowed_tool_names=allowed or None
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, test_case: Any) -> ExecutionTrace:
        """
        Execute a test case.

        Internal execution follows the existing AgentGuard runner flow.

        External execution is delegated to ExternalAgentAdapter and returns
        an ExecutionTrace compatible with the existing evaluation,
        security, observability, and reporting engines.
        """

        execution_type = getattr(
            self.agent_config,
            "execution_type",
            "internal",
        )

        if execution_type == "external":
            try:
                return ExternalAgentAdapter(self.agent_config).invoke(test_case)
            except Exception as exc:  # noqa: BLE001 - a broken adapter must fail the run, not crash it
                trace = ExecutionTrace(
                    agent_id=getattr(self.agent_config, "name", "unknown_agent"),
                    test_case_id=getattr(test_case, "id", "unknown_test_case"),
                )
                trace.mark_failed(f"External agent adapter failed: {exc}")
                return trace

        agent_id = getattr(
            self.agent_config,
            "name",
            "unknown_agent",
        )
        test_case_id = getattr(
            test_case,
            "id",
            "unknown_test_case",
        )
        user_input = self._get_user_input(test_case)

        # Isolate mock-tool state per run: the mock layer keeps module-global
        # state (e.g. issued refunds) that must not leak across runs in the
        # same process (e.g. sequential POST /runs against one API worker).
        reset = getattr(self.tool_registry, "reset", None)
        if callable(reset):
            reset()

        trace = ExecutionTrace(
            agent_id=agent_id,
            test_case_id=test_case_id,
        )

        try:
            messages: List[Dict[str, str]] = [
                {
                    "role": "system",
                    "content": self._get_system_prompt(),
                },
                {
                    "role": "user",
                    "content": user_input,
                },
            ]

            tool_schemas = self._build_tool_schemas()

            final_text: Optional[str] = None

            for turn in range(MAX_TURNS):
                llm_output = self._call_llm(
                    messages,
                    tool_schemas,
                    trace,
                )

                if llm_output.tool_calls:
                    # Feed the assistant's tool-call turn back into history.
                    messages.append(
                        {
                            "role": "assistant",
                            "content": llm_output.content or "",
                        }
                    )

                    for call in llm_output.tool_calls:
                        name = call["name"]
                        arguments = call.get("arguments", {})

                        self._execute_tool(
                            name,
                            arguments,
                            trace,
                            messages,
                        )

                    continue

                # No further tool calls -> this is the final answer.
                final_text = llm_output.content or ""
                break

            if final_text is None:
                raise AgentRunnerError(
                    f"Exceeded max turns ({MAX_TURNS}) "
                    "without a final response"
                )

            trace.add_event(
                FinalResponseEvent(
                    content=final_text,
                )
            )

            trace.mark_complete(
                final_response=final_text,
            )

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Agent run failed for test_case=%s",
                test_case_id,
            )
            trace.mark_failed(str(exc))

        return trace

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_allowed_tool_names(self) -> List[str]:
        permissions = getattr(
            self.agent_config,
            "permissions",
            None,
        )

        # Prefer permissions.allowed_tools when present.
        allowed = (
            getattr(
                permissions,
                "allowed_tools",
                None,
            )
            if permissions
            else None
        )

        # Backward compatibility: some configs store allowed_tools directly
        # on AgentConfig.
        if not allowed:
            allowed = getattr(
                self.agent_config,
                "allowed_tools",
                None,
            )

        return list(allowed) if allowed else []

    def _get_system_prompt(self) -> str:
        return (
            getattr(
                self.agent_config,
                "system_prompt",
                "",
            )
            or ""
        )

    def _get_user_input(self, test_case: Any) -> str:
        # Support the existing TestCase field and compatibility aliases.
        for attr in ("user_input", "input", "prompt"):
            if hasattr(test_case, attr):
                return getattr(test_case, attr)

        raise AgentRunnerError(
            "TestCase has no recognizable user input field"
        )

    def _build_tool_schemas(self) -> List[Dict[str, Any]]:
        tools = getattr(
            self.agent_config,
            "tools",
            [],
        ) or []

        allowed = set(
            self._get_allowed_tool_names()
        ) or {
            getattr(tool, "name")
            for tool in tools
        }

        schemas: List[Dict[str, Any]] = []

        for tool in tools:
            if tool.name not in allowed:
                continue

            properties: Dict[str, Any] = {}
            required: List[str] = []

            for param in getattr(
                tool,
                "parameters",
                [],
            ) or []:
                properties[param.name] = {
                    "type": param.type,
                    "description": param.description or "",
                }

                if param.required:
                    required.append(param.name)

            schemas.append(
                {
                    "name": tool.name,
                    "description": getattr(
                        tool,
                        "description",
                        "",
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                }
            )

        return schemas

    def _call_llm(
        self,
        messages: List[Dict[str, str]],
        tool_schemas: List[Dict[str, Any]],
        trace: ExecutionTrace,
    ):
        last_user_msg = next(
            (
                message["content"]
                for message in reversed(messages)
                if message["role"] == "user"
            ),
            "",
        )

        response = self.llm_provider.chat(
            messages=messages,
            tools=tool_schemas,
        )

        if not isinstance(response, dict):
            content = getattr(
                response,
                "content",
                None,
            )
            raw_tool_calls = getattr(
                response,
                "tool_calls",
                None,
            )
            prompt_tokens = getattr(
                response,
                "prompt_tokens",
                None,
            )
            completion_tokens = getattr(
                response,
                "completion_tokens",
                None,
            )
        else:
            content = response.get("content")
            raw_tool_calls = response.get("tool_calls")
            prompt_tokens = response.get("prompt_tokens")
            completion_tokens = response.get("completion_tokens")

        tool_calls = self._normalize_tool_calls(
            raw_tool_calls
        )

        trace.add_event(
            LLMCallEvent(
                input=last_user_msg,
                output=content,
                tool_calls_requested=[
                    tool_call["name"]
                    for tool_call in tool_calls
                ],
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        )

        return _LLMOutput(
            content=content,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _normalize_tool_calls(
        raw_tool_calls: Any,
    ) -> List[Dict[str, Any]]:
        if not raw_tool_calls:
            return []

        normalized: List[Dict[str, Any]] = []

        for tool_call in raw_tool_calls:
            if isinstance(tool_call, dict):
                normalized.append(
                    {
                        "name": tool_call["name"],
                        "arguments": tool_call.get(
                            "arguments",
                            {},
                        ),
                    }
                )
            else:
                normalized.append(
                    {
                        "name": tool_call.name,
                        "arguments": getattr(
                            tool_call,
                            "arguments",
                            {},
                        ),
                    }
                )

        return normalized

    def _execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        trace: ExecutionTrace,
        messages: List[Dict[str, str]],
    ) -> None:
        trace.add_event(
            ToolCallEvent(
                tool_name=name,
                arguments=arguments,
            )
        )

        allowed = self._get_allowed_tool_names()

        permissions = getattr(
            self.agent_config,
            "permissions",
            None,
        )

        blocked = (
            getattr(
                permissions,
                "blocked_tools",
                [],
            )
            if permissions
            else []
        )

        blocked = blocked or []

        if name in blocked or (
            allowed and name not in allowed
        ):
            error_msg = (
                f"Tool '{name}' is not permitted "
                "for this agent"
            )

            trace.add_event(
                ToolErrorEvent(
                    tool_name=name,
                    error=error_msg,
                )
            )

            messages.append(
                {
                    "role": "tool",
                    "content": f"ERROR: {error_msg}",
                }
            )
            return

        try:
            result = self.tool_registry.call(
                name,
                arguments,
            )

            trace.add_event(
                ToolResultEvent(
                    tool_name=name,
                    result=result,
                )
            )

            messages.append(
                {
                    "role": "tool",
                    "content": str(result),
                }
            )

        except MockToolError as exc:
            trace.add_event(
                ToolErrorEvent(
                    tool_name=name,
                    error=str(exc),
                )
            )

            messages.append(
                {
                    "role": "tool",
                    "content": f"ERROR: {exc}",
                }
            )


class _LLMOutput:
    """Small internal container for a uniform LLM response shape."""

    __slots__ = (
        "content",
        "tool_calls",
    )

    def __init__(
        self,
        content: Optional[str],
        tool_calls: List[Dict[str, Any]],
    ):
        self.content = content
        self.tool_calls = tool_calls