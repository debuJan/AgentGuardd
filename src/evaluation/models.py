"""
Strongly typed models for evaluation results.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class EvaluationCheck(BaseModel):
    """Result of a single evaluator."""

    name: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    message: str
    details: dict = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    """Aggregate result of running all evaluators against one ExecutionTrace."""

    run_id: str
    agent_id: str
    test_case_id: str
    passed: bool
    reliability_score: float = Field(ge=0.0, le=100.0)
    checks: List[EvaluationCheck] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    summary: str = ""

    def get_check(self, name: str) -> Optional[EvaluationCheck]:
        return next((c for c in self.checks if c.name == name), None)
