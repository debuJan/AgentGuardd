from typing import Optional

from src.core.config_models import AgentConfig, TestCase
from src.core.trace import ExecutionTrace
from src.evaluation.engine import EvaluationEngine
from src.observability.engine import ObservabilityEngine
from src.reporting.history.repository import ReportRepository
from src.reporting.models import UnifiedReportConfig, UnifiedRunReport
from src.reporting.scoring import UnifiedReportScorer
from src.security.engine import SecurityEngine


class ReportingEngine:
    """Unified engine aggregating Reliability, Security, and Observability metrics."""

    def __init__(
        self,
        eval_engine: Optional[EvaluationEngine] = None,
        security_engine: Optional[SecurityEngine] = None,
        observability_engine: Optional[ObservabilityEngine] = None,
        config: Optional[UnifiedReportConfig] = None,
        repository: Optional[ReportRepository] = None,
    ):
        self.eval_engine = eval_engine or EvaluationEngine()
        self.security_engine = security_engine or SecurityEngine()
        self.observability_engine = observability_engine or ObservabilityEngine()
        self.config = config or UnifiedReportConfig()
        self.scorer = UnifiedReportScorer(self.config)
        self.repository = repository

    def _resolve_agent_id(
        self,
        trace: ExecutionTrace,
        agent_config: AgentConfig,
    ) -> str:
        """Safely extracts agent identity across schema variations."""
        return (
            getattr(agent_config, "id", None)
            or getattr(agent_config, "name", None)
            or getattr(trace, "agent_id", None)
            or getattr(trace, "agent_name", None)
            or "unknown_agent"
        )

    def _resolve_test_case_id(
        self,
        trace: ExecutionTrace,
        test_case: TestCase,
    ) -> str:
        """Safely extracts test case identity across schema variations."""
        return (
            getattr(test_case, "id", None)
            or getattr(test_case, "name", None)
            or getattr(trace, "test_case_id", None)
            or getattr(trace, "test_case_name", None)
            or "unknown_test_case"
        )

    def generate(
        self,
        trace: ExecutionTrace,
        agent_config: AgentConfig,
        test_case: TestCase,
    ) -> UnifiedRunReport:
        # 1. Execute sub-engines with required arguments.
        # Both engines accept (trace, agent_config, test_case) as kwargs;
        # call them directly so internal TypeErrors surface instead of
        # being masked by positional-arg retry fallbacks.
        reliability_res = self.eval_engine.evaluate(
            trace=trace,
            agent_config=agent_config,
            test_case=test_case,
        )

        security_res = self.security_engine.evaluate(
            trace=trace,
            agent_config=agent_config,
            test_case=test_case,
        )

        metrics_res = self.observability_engine.analyze(
            trace,
            agent_config,
        )

        # 2. Score overall run deterministically
        overall_score, overall_status, failures = self.scorer.calculate(
            reliability=reliability_res,
            security=security_res,
        )

        # 3. Extract token metrics directly from metrics_res.tokens.total_tokens
        total_tokens = None
        if hasattr(metrics_res, "tokens") and metrics_res.tokens is not None:
            total_tokens = getattr(
                metrics_res.tokens,
                "total_tokens",
                None,
            )

        # 4. Extract cost metrics directly from metrics_res.cost.total_cost
        cost_usd = None
        if hasattr(metrics_res, "cost") and metrics_res.cost is not None:
            cost_usd = getattr(
                metrics_res.cost,
                "total_cost",
                None,
            )

        # 5. Extract duration safely, handling None values
        duration_ms = getattr(
            metrics_res,
            "duration_ms",
            0.0,
        )

        if duration_ms is None:
            duration_ms = 0.0

        # 6. Resolve IDs safely
        agent_id = self._resolve_agent_id(
            trace,
            agent_config,
        )

        test_case_id = self._resolve_test_case_id(
            trace,
            test_case,
        )

        report = UnifiedRunReport(
            run_id=trace.run_id,
            agent_id=agent_id,
            test_case_id=test_case_id,
            overall_status=overall_status,
            overall_score=overall_score,
            reliability=reliability_res,
            security=security_res,
            metrics=metrics_res,

            # Preserve the complete execution trace
            trace=trace,

            duration_ms=float(duration_ms),
            total_tokens=total_tokens,
            estimated_cost_usd=cost_usd,
            llm_call_count=getattr(
                metrics_res,
                "llm_call_count",
                0,
            ) or 0,
            tool_call_count=getattr(
                metrics_res,
                "tool_call_count",
                0,
            ) or 0,
            tool_error_count=getattr(
                metrics_res,
                "tool_error_count",
                0,
            ) or 0,
            repeated_tool_call_count=getattr(
                metrics_res,
                "repeated_tool_call_count",
                0,
            ) or 0,
            important_failures=failures,
        )

        # 7. Persist report when a repository is provided
        if self.repository is not None:
            self.repository.save(report)

        return report