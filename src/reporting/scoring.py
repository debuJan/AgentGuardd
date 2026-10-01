from typing import List, Tuple
from src.evaluation.models import EvaluationResult
from src.reporting.models import RunStatus, UnifiedReportConfig
from src.security.models import SecurityResult, Severity


class UnifiedReportScorer:
    """Calculates overall score and status deterministically without an LLM judge."""

    def __init__(self, config: UnifiedReportConfig = None):
        self.config = config or UnifiedReportConfig()

    def calculate(
        self,
        reliability: EvaluationResult,
        security: SecurityResult,
    ) -> Tuple[float, RunStatus, List[str]]:
        failures: List[str] = []

        # 1. Calculate weighted overall score
        total_weight = self.config.reliability_weight + self.config.security_weight
        if total_weight > 0:
            raw_score = (
                (reliability.reliability_score * self.config.reliability_weight) +
                (security.security_score * self.config.security_weight)
            ) / total_weight
        else:
            raw_score = 0.0

        overall_score = round(raw_score, 4)

        # 2. Collect reliability failures
        if not reliability.passed:
            failures.append("Reliability evaluation failed.")

        for check in reliability.checks:
            if not check.passed:
                failures.append(
                    f"Reliability Issue: {check.name}: {check.message}"
                )


        # 3. Hard-gate check on Security
        has_critical_security = False
        if not security.passed:
            failures.append("Security evaluation failed hard gate.")
            has_critical_security = True

        for finding in security.findings:
            sev = getattr(finding, "severity", None)
            desc = getattr(finding, "message", "Security vulnerability detected")
            sev_str = getattr(sev, "value", str(sev))

            if sev in (Severity.CRITICAL, Severity.HIGH) or str(sev_str).upper() in ("CRITICAL", "HIGH"):
                failures.append(f"Security Finding [{sev_str}]: {desc}")
                if sev == Severity.CRITICAL or str(sev_str).upper() == "CRITICAL":
                    has_critical_security = True

        # 4. Status Determination
        if has_critical_security or not security.passed:
            overall_status = RunStatus.FAIL
            # A security hard-gate failure must not present as a high
            # overall score next to the FAIL status.
            overall_score = 0.0
        elif not reliability.passed or overall_score < self.config.pass_threshold:
            overall_status = RunStatus.FAIL
        else:
            overall_status = RunStatus.PASS

        return overall_score, overall_status, failures