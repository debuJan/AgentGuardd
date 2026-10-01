"""
EvaluationEngine: orchestrates all evaluators against an ExecutionTrace
and produces a single EvaluationResult with a deterministic, explainable
reliability score.

Generic by design — contains no agent-specific (e.g. e-commerce) logic.
All behavior is driven by `agent_config` and `test_case`.
"""
from __future__ import annotations

import logging
from typing import Any, List

from src.core.trace import ExecutionTrace
from src.evaluation.base import BaseEvaluator
from src.evaluation.models import EvaluationCheck, EvaluationResult
from src.evaluation.outcome_evaluator import OutcomeConsistencyEvaluator, TaskSuccessEvaluator
from src.evaluation.latency_evaluator import MaxLatencyEvaluator
from src.evaluation.policy_evaluator import PolicyEvaluator
from src.evaluation.scoring import assign_weights, compute_score
from src.evaluation.tool_evaluator import (
    BlockedToolEvaluator,
    MaxToolCallsEvaluator,
    ToolArgumentEvaluator,
    ToolErrorEvaluator,
    ToolResultCoverageEvaluator,
    ToolSelectionEvaluator,
    ToolSequenceEvaluator,
    UnauthorizedToolEvaluator,
)

logger = logging.getLogger(__name__)

# Checks whose failure is a hard gate: if any of these fail, the run FAILS
# outright regardless of weighted score (security/permission violations
# should never be "partially fine").
HARD_GATE_CHECKS = {"unauthorized_tool_usage", "blocked_tool_usage"}

DEFAULT_EVALUATORS: List[BaseEvaluator] = [
    TaskSuccessEvaluator(),
    ToolSelectionEvaluator(),
    ToolArgumentEvaluator(),
    ToolSequenceEvaluator(),
    PolicyEvaluator(),
    UnauthorizedToolEvaluator(),
    BlockedToolEvaluator(),
    ToolErrorEvaluator(),
    OutcomeConsistencyEvaluator(),
    MaxToolCallsEvaluator(),
    ToolResultCoverageEvaluator(),
    MaxLatencyEvaluator(),
]


class EvaluationEngine:
    def __init__(self, evaluators: List[BaseEvaluator] | None = None):
        self.evaluators = evaluators if evaluators is not None else list(DEFAULT_EVALUATORS)

    def evaluate(self, trace: ExecutionTrace, agent_config: Any, test_case: Any) -> EvaluationResult:
        checks: List[EvaluationCheck] = []

        for evaluator in self.evaluators:
            try:
                check = evaluator.evaluate(trace, agent_config, test_case)
            except Exception as exc:  # noqa: BLE001 - a broken evaluator must not crash the whole run
                logger.exception("Evaluator '%s' raised an exception", getattr(evaluator, "name", evaluator))
                check = EvaluationCheck(
                    name=getattr(evaluator, "name", "unknown_evaluator"),
                    passed=False,
                    score=0.0,
                    weight=0.0,
                    message=f"Evaluator crashed: {exc}",
                )
            checks.append(check)

        assign_weights(checks)
        reliability_score = compute_score(checks)

        failures = [f"{c.name}: {c.message}" for c in checks if not c.passed]
        warnings = [
            f"{c.name}: {c.message}"
            for c in checks
            if c.passed and c.details.get("unchecked_policies")
        ]

        hard_gate_failed = any(not c.passed for c in checks if c.name in HARD_GATE_CHECKS)
        overall_passed = not hard_gate_failed and not failures

        if hard_gate_failed:
            reliability_score = min(reliability_score, 0.0)

        summary = self._build_summary(overall_passed, reliability_score, failures)

        return EvaluationResult(
            run_id=trace.run_id,
            agent_id=trace.agent_id,
            test_case_id=trace.test_case_id,
            passed=overall_passed,
            reliability_score=reliability_score,
            checks=checks,
            failures=failures,
            warnings=warnings,
            summary=summary,
        )

    @staticmethod
    def _build_summary(passed: bool, score: float, failures: List[str]) -> str:
        if passed:
            return f"PASSED — reliability score {score}/100."
        reasons = "; ".join(failures) if failures else "hard-gate security violation."
        return f"FAILED — reliability score {score}/100. Reasons: {reasons}"
