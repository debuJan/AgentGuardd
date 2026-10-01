"""
Base evaluator interface. All concrete evaluators implement `evaluate`
and return a single EvaluationCheck. The engine assigns the weight.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.core.trace import ExecutionTrace
from src.evaluation.models import EvaluationCheck


class BaseEvaluator(ABC):
    #: unique check name, used as the key in scoring.WEIGHTS
    name: str = "base"

    @abstractmethod
    def evaluate(self, trace: ExecutionTrace, agent_config: Any, test_case: Any) -> EvaluationCheck:
        """Run this evaluator and return a single EvaluationCheck (weight is 0 here; engine fills it in)."""
        raise NotImplementedError

    def _check(self, passed: bool, score: float, message: str, details: dict | None = None) -> EvaluationCheck:
        return EvaluationCheck(
            name=self.name,
            passed=passed,
            score=max(0.0, min(1.0, score)),
            weight=0.0,  # filled in by the engine from scoring.WEIGHTS
            message=message,
            details=details or {},
        )
