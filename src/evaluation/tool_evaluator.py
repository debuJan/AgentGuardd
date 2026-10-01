"""
Tool-related evaluators.

These evaluators read expectations from `test_case.expected_tool_calls`.

Each expected tool call contains:
    - tool
    - arguments
    - order

The evaluators check:
    - expected/missing/unexpected tools
    - duplicate tool calls
    - tool arguments for every call
    - tool execution order
    - unauthorized tools
    - blocked tools
    - tool errors
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.core.config_models import resolve_allowed_tools, resolve_blocked_tools
from src.core.trace import ExecutionTrace, ToolCallEvent, ToolErrorEvent, ToolResultEvent
from src.evaluation.base import BaseEvaluator
from src.evaluation.models import EvaluationCheck


def _get_expected_tools(test_case: Any) -> List[str]:
    expected_calls = getattr(test_case, "expected_tool_calls", None) or []
    return [call.tool for call in expected_calls]


def _get_expected_sequence(test_case: Any) -> List[str]:
    expected_calls = getattr(test_case, "expected_tool_calls", None) or []

    ordered_calls = sorted(
        expected_calls,
        key=lambda call: (
            call.order is None,
            call.order if call.order is not None else 0,
        ),
    )

    return [call.tool for call in ordered_calls]


def _get_expected_arguments(test_case: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Map tool name -> list of expected argument dicts.

    A list (not a single dict) so repeated expected calls to the same tool
    with different arguments do not collapse into one entry.
    """
    expected_calls = getattr(test_case, "expected_tool_calls", None) or []

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for call in expected_calls:
        if call.arguments is not None:
            grouped.setdefault(call.tool, []).append(call.arguments)
    return grouped


def _tool_calls(trace: ExecutionTrace) -> List[ToolCallEvent]:
    return [e for e in trace.events if isinstance(e, ToolCallEvent)]


class ToolSelectionEvaluator(BaseEvaluator):
    """Did the agent call all expected tools and avoid unexpected/duplicate calls?"""

    name = "tool_selection"

    def evaluate(
        self,
        trace: ExecutionTrace,
        agent_config: Any,
        test_case: Any,
    ) -> EvaluationCheck:

        expected_tools = _get_expected_tools(test_case)

        if not expected_tools:
            return self._check(
                True,
                1.0,
                "No expected tools configured; skipping.",
                {"skipped": True},
            )

        # Keep the original list so duplicate calls are not lost.
        actual_tools = [tc.tool_name for tc in _tool_calls(trace)]

        expected = set(expected_tools)
        actual = set(actual_tools)

        missing = expected - actual
        extra = actual - expected

        # Detect duplicate/repeated tool calls.
        seen = set()
        duplicates = []

        for tool in actual_tools:
            if tool in seen:
                duplicates.append(tool)
            else:
                seen.add(tool)

        # Everything is correct only when:
        # - no expected tool is missing
        # - no unexpected tool was called
        # - no tool was called more than once
        if not missing and not extra and not duplicates:
            return self._check(
                True,
                1.0,
                "All expected tools were called exactly once.",
                {
                    "expected": sorted(expected),
                    "actual": actual_tools,
                },
            )

        overlap = len(expected & actual)
        score = overlap / len(expected) if expected else 0.0

        msg_parts = []

        if missing:
            msg_parts.append(f"missing: {sorted(missing)}")

        if extra:
            msg_parts.append(f"unexpected: {sorted(extra)}")

        if duplicates:
            msg_parts.append(
                f"duplicate calls: {sorted(set(duplicates))}"
            )

        return self._check(
            False,
            score,
            "Tool selection mismatch (" + "; ".join(msg_parts) + ").",
            {
                "expected": sorted(expected),
                "actual": actual_tools,
                "missing": sorted(missing),
                "extra": sorted(extra),
                "duplicates": sorted(set(duplicates)),
            },
        )


class ToolArgumentEvaluator(BaseEvaluator):
    """Do actual tool call arguments match expected arguments?"""

    name = "tool_arguments"

    def evaluate(
        self,
        trace: ExecutionTrace,
        agent_config: Any,
        test_case: Any,
    ) -> EvaluationCheck:

        expected_args = _get_expected_arguments(test_case)

        if not expected_args:
            return self._check(
                True,
                1.0,
                "No expected arguments configured; skipping.",
                {"skipped": True},
            )

        # Store ALL calls for every tool.
        #
        # Previously this used:
        #
        #     setdefault(tool_name, arguments)
        #
        # which kept only the first call.
        #
        # Now repeated calls are preserved and checked.
        calls_by_tool: Dict[str, List[Dict[str, Any]]] = {}

        for tc in _tool_calls(trace):
            calls_by_tool.setdefault(
                tc.tool_name,
                [],
            ).append(tc.arguments)

        total = len(expected_args)
        correct = 0
        mismatches = {}

        for tool_name, expected_specs in expected_args.items():
            actual_calls = calls_by_tool.get(tool_name, [])

            # Expected tool wasn't called at all.
            if not actual_calls:
                mismatches[tool_name] = {
                    "reason": "tool was not called",
                    "expected": expected_specs,
                }
                continue

            # One-to-one coverage: each expected spec must be satisfied by a
            # DISTINCT actual call (greedy bipartite match in spec order).
            # This catches e.g. expected [{id:1},{id:2}] with actual
            # [{id:1},{id:1}] -- the {id:2} spec is never observed.
            def _spec_matches(spec: Dict[str, Any], actual: Dict[str, Any]) -> bool:
                return all(actual.get(key) == value for key, value in spec.items())

            consumed = [False] * len(actual_calls)
            unmatched_specs = []
            for spec in expected_specs:
                found = False
                for i, actual in enumerate(actual_calls):
                    if not consumed[i] and _spec_matches(spec, actual):
                        consumed[i] = True
                        found = True
                        break
                if not found:
                    unmatched_specs.append(spec)

            incorrect_calls = [
                actual
                for actual, used in zip(actual_calls, consumed)
                if not used and not any(_spec_matches(spec, actual) for spec in expected_specs)
            ]

            if unmatched_specs or incorrect_calls:
                mismatches[tool_name] = {
                    "expected": expected_specs,
                    "actual_calls": actual_calls,
                    "unmatched_expected_specs": unmatched_specs,
                    "incorrect_calls": incorrect_calls,
                }
            else:
                correct += 1

        score = correct / total if total else 1.0

        if not mismatches:
            return self._check(
                True,
                1.0,
                "All tool arguments matched expectations.",
                {
                    "checked": list(expected_args),
                    "calls": calls_by_tool,
                },
            )

        return self._check(
            False,
            score,
            f"Argument mismatch for tools: {list(mismatches)}.",
            {
                "mismatches": mismatches,
            },
        )


class ToolSequenceEvaluator(BaseEvaluator):
    """If an expected sequence is configured, did the agent follow it?"""

    name = "tool_sequence"

    def evaluate(
        self,
        trace: ExecutionTrace,
        agent_config: Any,
        test_case: Any,
    ) -> EvaluationCheck:

        expected_sequence = _get_expected_sequence(test_case)

        if not expected_sequence:
            return self._check(
                True,
                1.0,
                "No expected sequence configured; skipping.",
                {"skipped": True},
            )

        actual_sequence = [
            tc.tool_name
            for tc in _tool_calls(trace)
        ]

        # Check whether expected_sequence appears in order
        # as a subsequence of actual_sequence.
        idx = 0

        for tool in actual_sequence:
            if (
                idx < len(expected_sequence)
                and tool == expected_sequence[idx]
            ):
                idx += 1

        matched = idx

        if matched == len(expected_sequence):
            return self._check(
                True,
                1.0,
                "Tools were called in the expected order.",
                {
                    "expected": expected_sequence,
                    "actual": actual_sequence,
                },
            )

        score = (
            matched / len(expected_sequence)
            if expected_sequence
            else 0.0
        )

        return self._check(
            False,
            score,
            "Tool call order did not match the expected sequence.",
            {
                "expected": expected_sequence,
                "actual": actual_sequence,
                "matched_prefix_len": matched,
            },
        )


class UnauthorizedToolEvaluator(BaseEvaluator):
    """Did the agent call any tool outside its allowed_tools?"""

    name = "unauthorized_tool_usage"

    def evaluate(
        self,
        trace: ExecutionTrace,
        agent_config: Any,
        test_case: Any,
    ) -> EvaluationCheck:

        # Read from AgentConfig.permissions (canonical) with legacy fallback.
        allowed = set(resolve_allowed_tools(agent_config))

        actual = {
            tc.tool_name
            for tc in _tool_calls(trace)
        }

        if not allowed:
            return self._check(
                True,
                1.0,
                "No allowed_tools restriction configured; skipping.",
                {"skipped": True},
            )

        unauthorized = actual - allowed

        if not unauthorized:
            return self._check(
                True,
                1.0,
                "No unauthorized tool calls detected.",
                {
                    "allowed": sorted(allowed),
                },
            )

        return self._check(
            False,
            0.0,
            f"Unauthorized tools called: {sorted(unauthorized)}.",
            {
                "unauthorized": sorted(unauthorized),
                "allowed": sorted(allowed),
            },
        )


class BlockedToolEvaluator(BaseEvaluator):
    """Did the agent attempt to call an explicitly blocked tool?"""

    name = "blocked_tool_usage"

    def evaluate(
        self,
        trace: ExecutionTrace,
        agent_config: Any,
        test_case: Any,
    ) -> EvaluationCheck:

        # Read from AgentConfig.permissions (canonical) with legacy fallback.
        blocked = set(resolve_blocked_tools(agent_config))

        actual = {
            tc.tool_name
            for tc in _tool_calls(trace)
        }

        attempted_blocked = actual & blocked

        if not attempted_blocked:
            return self._check(
                True,
                1.0,
                "No blocked tools were attempted.",
                {
                    "blocked": sorted(blocked),
                },
            )

        return self._check(
            False,
            0.0,
            f"Blocked tools were attempted: "
            f"{sorted(attempted_blocked)}.",
            {
                "attempted_blocked": sorted(attempted_blocked),
            },
        )


class ToolErrorEvaluator(BaseEvaluator):
    """Did any tool call result in an error?"""

    name = "tool_errors"

    def evaluate(
        self,
        trace: ExecutionTrace,
        agent_config: Any,
        test_case: Any,
    ) -> EvaluationCheck:

        errors = [
            e
            for e in trace.events
            if isinstance(e, ToolErrorEvent)
        ]

        total_calls = len(_tool_calls(trace))

        if not errors:
            return self._check(
                True,
                1.0,
                "No tool errors occurred.",
                {},
            )

        error_rate = (
            len(errors) / total_calls
            if total_calls
            else 1.0
        )

        return self._check(
            False,
            max(0.0, 1.0 - error_rate),
            f"{len(errors)} tool error(s) occurred: "
            + ", ".join(
                f"{e.tool_name} ({e.error})"
                for e in errors
            ),
            {
                "errors": [
                    {
                        "tool_name": e.tool_name,
                        "error": e.error,
                    }
                    for e in errors
                ]
            },
        )

class MaxToolCallsEvaluator(BaseEvaluator):
    """Did the agent stay within the configured max_tool_calls budget?"""

    name = "max_tool_calls"

    def evaluate(
        self,
        trace: ExecutionTrace,
        agent_config: Any,
        test_case: Any,
    ) -> EvaluationCheck:
        max_calls = getattr(test_case, "max_tool_calls", None)

        if max_calls is None:
            return self._check(
                True,
                1.0,
                "No max_tool_calls configured; skipping.",
                {"skipped": True},
            )

        count = len(_tool_calls(trace))

        if count <= max_calls:
            return self._check(
                True,
                1.0,
                f"Tool calls within budget ({count}/{max_calls}).",
                {"tool_calls": count, "max_tool_calls": max_calls},
            )

        return self._check(
            False,
            0.0,
            f"Tool call budget exceeded: {count} calls (max {max_calls}).",
            {"tool_calls": count, "max_tool_calls": max_calls},
        )


class ToolResultCoverageEvaluator(BaseEvaluator):
    """Does every tool call have a matching result or error event?

    A call with no recorded outcome means the trace is incomplete — the
    agent's action cannot be audited, so the run cannot be trusted.
    """

    name = "tool_result_coverage"

    def evaluate(
        self,
        trace: ExecutionTrace,
        agent_config: Any,
        test_case: Any,
    ) -> EvaluationCheck:
        pending: List[tuple] = []  # (event_index, tool_name) awaiting outcome
        orphan_results: List[str] = []

        for idx, event in enumerate(trace.events):
            if isinstance(event, ToolCallEvent):
                pending.append((idx, event.tool_name))
            elif isinstance(event, (ToolResultEvent, ToolErrorEvent)):
                for i, (_, call_name) in enumerate(pending):
                    if call_name == event.tool_name:
                        pending.pop(i)
                        break
                else:
                    orphan_results.append(event.tool_name)

        details = {
            "unresolved_calls": [
                {"event_index": i, "tool_name": name}
                for i, name in pending
            ],
            "orphan_results": orphan_results,
        }

        if not pending:
            return self._check(
                True,
                1.0,
                "Every tool call has a recorded result or error.",
                details,
            )

        missing = ", ".join(
            f"{name} (event {i})" for i, name in pending
        )
        return self._check(
            False,
            0.0,
            f"{len(pending)} tool call(s) have no recorded result or error: {missing}.",
            details,
        )
