from typing import Dict, List, Optional

from src.core.config_models import TestCase
from src.reporting.history.repository import ReportRepository, TestCaseRepository
from src.reporting.models import UnifiedRunReport


class InMemoryReportRepository(ReportRepository):

    def __init__(self) -> None:
        self._storage: Dict[str, UnifiedRunReport] = {}
        # Monotonic sequence so list_runs is deterministic newest-first,
        # matching the Postgres repository's created_at ordering.
        self._seq: Dict[str, int] = {}
        self._counter = 0

    def save(self, report: UnifiedRunReport) -> None:
        if report.run_id in self._storage:
            raise ValueError(
                f"Report with run_id '{report.run_id}' already exists."
            )
        self._storage[report.run_id] = report
        self._counter += 1
        self._seq[report.run_id] = self._counter

    def get(self, run_id: str) -> Optional[UnifiedRunReport]:
        return self._storage.get(run_id)

    def list_runs(
        self,
        agent_id: Optional[str] = None,
        test_case_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[UnifiedRunReport]:
        if limit < 1:
            raise ValueError("Limit must be greater than or equal to 1.")

        results: List[UnifiedRunReport] = []
        for report in self._storage.values():
            if agent_id is not None and report.agent_id != agent_id:
                continue
            if test_case_id is not None and report.test_case_id != test_case_id:
                continue
            results.append(report)
        # Newest first (deterministic); run_id breaks ties.
        results.sort(key=lambda r: (-self._seq.get(r.run_id, 0), r.run_id))
        return results[:limit]

    def delete(self, run_id: str) -> bool:
        if run_id in self._storage:
            del self._storage[run_id]
            self._seq.pop(run_id, None)
            return True
        return False


class InMemoryTestCaseRepository(TestCaseRepository):
    """In-memory test-case library (local dev / tests)."""

    def __init__(self) -> None:
        self._storage: Dict[str, TestCase] = {}
        # Monotonic sequence so list() is deterministic newest-first,
        # matching the Postgres repository's created_at ordering.
        self._seq: Dict[str, int] = {}
        self._counter = 0

    def save(self, test_case: TestCase) -> None:
        if test_case.id in self._storage:
            raise ValueError(
                f"Test case with id '{test_case.id}' already exists."
            )
        self._storage[test_case.id] = test_case
        self._counter += 1
        self._seq[test_case.id] = self._counter

    def get(self, test_case_id: str) -> Optional[TestCase]:
        return self._storage.get(test_case_id)

    def list(
        self,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[TestCase]:
        if limit < 1:
            raise ValueError("Limit must be greater than or equal to 1.")

        results: List[TestCase] = []
        for case in self._storage.values():
            if category is not None and case.category.value != category:
                continue
            results.append(case)
        # Newest first (deterministic); id breaks ties.
        results.sort(key=lambda c: (-self._seq.get(c.id, 0), c.id))
        return results[:limit]

    def delete(self, test_case_id: str) -> bool:
        if test_case_id in self._storage:
            del self._storage[test_case_id]
            self._seq.pop(test_case_id, None)
            return True
        return False