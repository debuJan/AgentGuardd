from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TokenStatus(str, Enum):
    MEASURED = "measured"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class RunStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    ERROR = "error"
    INTERRUPTED = "interrupted"


class StepMetrics(BaseModel):
    step_index: int
    event_type: str
    event_name: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Event-gap approximation (see compute_step_latencies), not measured
    # execution time. None for the final event.
    duration_ms: Optional[float] = None
    status: str = "success"
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    error_message: Optional[str] = None


class TokenMetrics(BaseModel):
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    status: TokenStatus = TokenStatus.UNAVAILABLE


class CostBreakdown(BaseModel):
    input_cost: Optional[float] = None
    output_cost: Optional[float] = None
    total_cost: Optional[float] = None
    currency: str = "USD"
    status: TokenStatus = TokenStatus.UNAVAILABLE


class ModelPricingConfig(BaseModel):
    model_name: str
    input_cost_per_1m: float
    output_cost_per_1m: float
    currency: str = "USD"


class RunMetrics(BaseModel):
    run_id: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    status: RunStatus = RunStatus.SUCCESS

    llm_call_count: int = 0
    tool_call_count: int = 0
    tool_error_count: int = 0
    llm_error_count: int = 0
    repeated_tool_call_count: int = 0
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    tool_errors: List[Dict[str, Any]] = Field(default_factory=list)
    repeated_tool_calls: List[Dict[str, Any]] = Field(default_factory=list)

    tokens: TokenMetrics = Field(default_factory=TokenMetrics)
    cost: CostBreakdown = Field(default_factory=CostBreakdown)

    step_metrics: List[StepMetrics] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)