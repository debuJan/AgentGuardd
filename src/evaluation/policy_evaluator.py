"""
Policy compliance evaluator.

ADAPT: Policy objects' exact shape wasn't available here. This evaluator
looks for structured, deterministically-checkable policies of the form
"before_tool must be called before after_tool", using whichever of these
attribute names is present on each Policy:

    policy.before_tool / policy.after_tool
    policy.rule (a dict like {"before": "get_order", "after": "issue_refund"})

Policies that don't expose a structured rule are reported as WARNINGS
(cannot be deterministically checked yet) rather than silently ignored
or hard-failed — this keeps the engine honest without guessing intent.
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

from src.core.trace import ExecutionTrace, ToolCallEvent, ToolResultEvent
from src.evaluation.base import BaseEvaluator
from src.evaluation.models import EvaluationCheck


def _extract_before_after(policy: Any) -> Optional[Tuple[str, str]]:
    before = getattr(policy, "before_tool", None)
    after = getattr(policy, "after_tool", None)
    if before and after:
        return before, after

    rule = getattr(policy, "rule", None)
    if isinstance(rule, dict) and rule.get("before") and rule.get("after"):
        return rule["before"], rule["after"]

    return None


def _extract_precondition(policy: Any) -> Optional[Tuple[str, dict]]:
    """Extract a PRECONDITION rule: (tool, required_prior_result_subset).

    Documented rule shape:
        {"tool": "issue_refund", "requires_prior_tool_result": {"eligible": True}}
    """
    rule = getattr(policy, "rule", None)
    if not isinstance(rule, dict):
        return None
    tool = rule.get("tool")
    required = rule.get("requires_prior_tool_result")
    if tool and isinstance(required, dict) and required:
        return tool, required
    return None


def _result_satisfies(result: Any, required: dict) -> bool:
    """Subset match: every required key/value is present in the result dict."""
    if not isinstance(result, dict):
        return False
    return all(result.get(key) == value for key, value in required.items())


def check_precondition_violations(
    events: List[Any], tool: str, required: dict
) -> List[int]:
    """Return event indices of calls to `tool` with no prior satisfying result."""
    violations: List[int] = []
    for idx, event in enumerate(events):
        if not isinstance(event, ToolCallEvent) or event.tool_name != tool:
            continue
        satisfied = any(
            isinstance(prior, ToolResultEvent) and _result_satisfies(prior.result, required)
            for prior in events[:idx]
        )
        if not satisfied:
            violations.append(idx)
    return violations


class PolicyEvaluator(BaseEvaluator):
    name = "policy_compliance"

    def evaluate(self, trace: ExecutionTrace, agent_config: Any, test_case: Any) -> EvaluationCheck:
        policies: List[Any] = list(getattr(agent_config, "policies", None) or [])
        if not policies:
            return self._check(True, 1.0, "No policies configured; skipping.", {"skipped": True})

        call_order = [e.tool_name for e in trace.events if isinstance(e, ToolCallEvent)]

        violations = []
        unchecked = []

        for policy in policies:
            policy_name = getattr(policy, "name", str(policy))
            pair = _extract_before_after(policy)
            if pair is not None:
                before, after = pair
                if before not in call_order or after not in call_order:
                    # Policy doesn't apply if neither tool was involved
                    continue
                if call_order.index(before) > call_order.index(after):
                    violations.append(f"'{policy_name}': expected '{before}' before '{after}'")
                continue

            precondition = _extract_precondition(policy)
            if precondition is not None:
                tool, required = precondition
                bad_indices = check_precondition_violations(trace.events, tool, required)
                for bad_idx in bad_indices:
                    violations.append(
                        f"'{policy_name}': '{tool}' was called without a prior "
                        f"tool result satisfying {required} (event {bad_idx})"
                    )
                continue

            unchecked.append(policy_name)

        details = {"violations": violations, "unchecked_policies": unchecked, "call_order": call_order}

        if violations:
            score = max(0.0, 1.0 - (len(violations) / max(len(policies), 1)))
            return self._check(False, score, "Policy violation(s): " + "; ".join(violations), details)

        message = "No policy violations detected."
        if unchecked:
            message += f" ({len(unchecked)} policy(ies) could not be deterministically checked: {unchecked})"
        return self._check(True, 1.0, message, details)
