"""FastAPI dependencies: lazily-initialized repository and reporting engine.

The repository is created on first use, not at import time, so the API can
start (and serve /health) even when Postgres is unreachable. Repository
failures surface as HTTP 503 on the routes that need the repository.
"""
import os
import threading

from fastapi import HTTPException, status

from src.reporting.history.memory import InMemoryReportRepository, InMemoryTestCaseRepository
from src.reporting.history.postgres import PostgresReportRepository, PostgresTestCaseRepository
from src.reporting.history.repository import ReportRepository, TestCaseRepository
from src.reporting.engine import ReportingEngine


def _create_repository() -> ReportRepository:
    use_postgres = os.getenv("USE_POSTGRES", "true").lower() == "true"

    if use_postgres:
        return PostgresReportRepository()

    return InMemoryReportRepository()


def _create_test_case_repository() -> TestCaseRepository:
    use_postgres = os.getenv("USE_POSTGRES", "true").lower() == "true"

    if use_postgres:
        return PostgresTestCaseRepository()

    return InMemoryTestCaseRepository()


_lock = threading.Lock()
_repository_instance: ReportRepository | None = None
_repository_error: Exception | None = None
_test_case_repository_instance: TestCaseRepository | None = None
_test_case_repository_error: Exception | None = None


def get_repository() -> ReportRepository:
    """Return the shared repository, creating it lazily on first use."""
    global _repository_instance, _repository_error
    if _repository_instance is None and _repository_error is None:
        with _lock:
            if _repository_instance is None and _repository_error is None:
                try:
                    _repository_instance = _create_repository()
                except Exception as exc:  # noqa: BLE001 - surfaced as 503 below
                    _repository_error = exc
    if _repository_error is not None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Report repository unavailable: {_repository_error}",
        )
    return _repository_instance


def reset_repository() -> None:
    """Test hook: drop the cached repositories so the next call re-creates them."""
    global _repository_instance, _repository_error
    global _test_case_repository_instance, _test_case_repository_error
    with _lock:
        _repository_instance = None
        _repository_error = None
        _test_case_repository_instance = None
        _test_case_repository_error = None


def get_test_case_repository() -> TestCaseRepository:
    """Return the shared test-case library, creating it lazily on first use."""
    global _test_case_repository_instance, _test_case_repository_error
    if _test_case_repository_instance is None and _test_case_repository_error is None:
        with _lock:
            if _test_case_repository_instance is None and _test_case_repository_error is None:
                try:
                    _test_case_repository_instance = _create_test_case_repository()
                except Exception as exc:  # noqa: BLE001 - surfaced as 503 below
                    _test_case_repository_error = exc
    if _test_case_repository_error is not None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Test case repository unavailable: {_test_case_repository_error}",
        )
    return _test_case_repository_instance


def get_reporting_engine() -> ReportingEngine:
    return ReportingEngine(repository=get_repository())
