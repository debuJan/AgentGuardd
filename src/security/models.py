"""
Strongly typed models for the security engine.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SecurityFinding(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: str
    severity: Severity
    passed: bool = False  # a finding object represents a violation, so default False
    message: str
    evidence: Optional[str] = None  # must be pre-redacted by the check before constructing this
    event_index: Optional[int] = None
    rule_id: Optional[str] = None


class SecurityResult(BaseModel):
    run_id: str
    agent_id: str
    test_case_id: str
    passed: bool
    security_score: float = Field(ge=0.0, le=100.0)
    findings: List[SecurityFinding] = Field(default_factory=list)
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    summary: str = ""
