from typing import List, Optional
from pydantic import BaseModel, Field

from src.core.config_models import (
    AgentConfig,
    ExpectedToolCall,
    SecurityExpectation,
    TestCase,
    TestCaseCategory,
)
from src.core.trace import ExecutionTrace
from src.reporting.models import UnifiedRunReport


class HealthResponse(BaseModel):
    status: str = "ok"
    database: str = "unknown"


class TestCaseCreate(BaseModel):
    """Payload for authoring a reusable test case in the library.

    ``id`` is optional: when omitted the server assigns ``tc_<uuid8>``.
    Every other field mirrors :class:`TestCase` so a stored case can be
    passed straight back into ``POST /runs``.
    """

    id: Optional[str] = None
    title: Optional[str] = None
    agent_name: str = "unspecified"
    category: TestCaseCategory = TestCaseCategory.FUNCTIONAL
    user_input: str
    expected_tool_calls: List[ExpectedToolCall] = Field(default_factory=list)
    expected_outcome: Optional[str] = None
    security_expectation: SecurityExpectation = Field(
        default_factory=SecurityExpectation
    )
    max_tool_calls: Optional[int] = None
    max_latency_ms: Optional[int] = None

    def to_test_case(self, test_case_id: str) -> TestCase:
        return TestCase(
            id=test_case_id,
            title=self.title,
            agent_name=self.agent_name,
            category=self.category,
            user_input=self.user_input,
            expected_tool_calls=self.expected_tool_calls,
            expected_outcome=self.expected_outcome,
            security_expectation=self.security_expectation,
            max_tool_calls=self.max_tool_calls,
            max_latency_ms=self.max_latency_ms,
        )


class TestCaseListResponse(BaseModel):
    test_cases: List[TestCase]
    count: int


class RunExecutionRequest(BaseModel):
    """Runs an agent from its configuration and test case.

    The test case can be supplied inline (``test_case``) or by reference
    (``test_case_id``, resolved against the test-case library). Exactly one
    of the two must be provided.
    """
    agent_config: AgentConfig
    test_case: Optional[TestCase] = None
    test_case_id: Optional[str] = None
    trace: Optional[ExecutionTrace] = None


class RunReportListResponse(BaseModel):
    reports: List[UnifiedRunReport]
    count: int