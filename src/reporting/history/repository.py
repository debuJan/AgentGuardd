from abc import ABC, abstractmethod
from typing import List, Optional

from src.core.config_models import TestCase
from src.reporting.models import UnifiedRunReport


class ReportRepository(ABC):

    @abstractmethod
    def save(self, report: UnifiedRunReport) -> None:
        pass

    @abstractmethod
    def get(self, run_id: str) -> Optional[UnifiedRunReport]:
        pass

    @abstractmethod
    def list_runs(
        self,
        agent_id: Optional[str] = None,
        test_case_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[UnifiedRunReport]:
        pass

    @abstractmethod
    def delete(self, run_id: str) -> bool:
        pass


class TestCaseRepository(ABC):
    """Persistent library of evaluation test cases.

    Test cases are the reusable "exam questions" of the platform: they are
    authored once (via ``POST /test-cases`` or the dashboard), stored here,
    and referenced by id when a run is triggered (``POST /runs`` with
    ``test_case_id``). Mirrors the ReportRepository backend split: Postgres
    in production, in-memory when ``USE_POSTGRES=false``.
    """

    @abstractmethod
    def save(self, test_case: TestCase) -> None:
        """Store a test case. Raises ValueError if the id already exists."""
        pass

    @abstractmethod
    def get(self, test_case_id: str) -> Optional[TestCase]:
        pass

    @abstractmethod
    def list(
        self,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[TestCase]:
        pass

    @abstractmethod
    def delete(self, test_case_id: str) -> bool:
        pass