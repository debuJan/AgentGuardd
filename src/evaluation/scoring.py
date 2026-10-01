"""
Deterministic scoring.

Weights sum to 1.0. Each evaluator's `score` (0-1) is multiplied by its
weight to produce a weighted contribution; the sum, scaled to 0-100, is
the reliability_score. This is fully transparent — no LLM-judged scores.
"""
from __future__ import annotations

from typing import Dict, List

from src.evaluation.models import EvaluationCheck

# Must sum to 1.0. Extend/rebalance as new evaluators are added.
WEIGHTS: Dict[str, float] = {
    "task_success": 0.20,
    "tool_selection": 0.16,
    "tool_arguments": 0.12,
    "tool_sequence": 0.07,
    "policy_compliance": 0.12,
    "tool_errors": 0.05,
    "outcome_consistency": 0.08,
    "max_tool_calls": 0.05,
    "tool_result_coverage": 0.08,
    "max_latency": 0.07,
    # Unauthorized/blocked tool usage are treated as hard gates (see engine.py)
    # rather than weighted scores, since any occurrence should dominate the result.
}


def assign_weights(checks: List[EvaluationCheck]) -> None:
    """Mutates each check in place, setting `weight` from WEIGHTS (0.0 if not listed)."""
    import logging

    logger = logging.getLogger(__name__)
    for check in checks:
        if check.name not in WEIGHTS:
            logger.warning(
                "Evaluation check '%s' has no registered weight; "
                "it will contribute 0.0 to the score.",
                check.name,
            )
        check.weight = WEIGHTS.get(check.name, 0.0)


def compute_score(checks: List[EvaluationCheck]) -> float:
    """Weighted sum of check.score * check.weight, scaled to 0-100."""
    total = sum(c.score * c.weight for c in checks)
    return round(total * 100, 2)
