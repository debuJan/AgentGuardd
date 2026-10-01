from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.core.trace import ExecutionTrace
from src.evaluation.models import EvaluationResult
from src.observability.models import RunMetrics
from src.security.models import SecurityResult


class RunStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class UnifiedReportConfig(BaseModel):
    reliability_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    security_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    pass_threshold: float = Field(default=70.0, ge=0.0, le=100.0)


class UnifiedRunReport(BaseModel):
    run_id: str
    agent_id: str
    test_case_id: str
    overall_status: RunStatus
    overall_score: float

    reliability: EvaluationResult
    security: SecurityResult
    metrics: RunMetrics

    # Complete execution trace
    trace: Optional[ExecutionTrace] = None

    # Key extracted operational metrics
    duration_ms: float = 0.0
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    llm_call_count: int = 0
    tool_call_count: int = 0
    tool_error_count: int = 0
    repeated_tool_call_count: int = 0

    important_failures: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)