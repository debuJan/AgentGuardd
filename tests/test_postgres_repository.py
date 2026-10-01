"""Postgres repository tests — skipped when no database is reachable."""
import uuid

import pytest

from src.reporting.engine import ReportingEngine
from src.reporting.history.postgres import PostgresReportRepository


def _unique_run_id(prefix: str) -> str:
    # Unique per test invocation: immune to stale rows left by interrupted runs.
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _postgres_available() -> bool:
    try:
        repo = PostgresReportRepository()
    except Exception:
        return False
    try:
        repo.list_runs(limit=1)
        return True
    except Exception:
        return False


needs_postgres = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL is not reachable (set DATABASE_URL / start compose).",
)


@needs_postgres
def test_postgres_repository_save_and_get(clean_trace, agent_config, test_case):
    # Generate a real UnifiedRunReport using the existing reporting engine.
    clean_trace.run_id = _unique_run_id("run_clean")
    engine = ReportingEngine()
    report = engine.generate(clean_trace, agent_config, test_case)

    repo = PostgresReportRepository()

    # Save the report to PostgreSQL.
    repo.save(report)

    try:
        # Read it back from PostgreSQL.
        loaded = repo.get(report.run_id)

        assert loaded is not None
        assert loaded.run_id == report.run_id
        assert loaded.agent_id == report.agent_id
        assert loaded.test_case_id == report.test_case_id
        assert loaded.overall_score == report.overall_score
    finally:
        # The real database persists across runs: always clean up.
        repo.delete(report.run_id)


@needs_postgres
def test_postgres_repository_list_runs_newest_first(clean_trace, agent_config, test_case):
    import time

    engine = ReportingEngine()
    repo = PostgresReportRepository()

    run_ids = []
    prefix = _unique_run_id("pg_order")
    for i in range(3):
        clean_trace.run_id = f"{prefix}_{i}"
        report = engine.generate(clean_trace, agent_config, test_case)
        repo.save(report)
        run_ids.append(report.run_id)
        time.sleep(0.01)

    try:
        listed = repo.list_runs(limit=10)
        listed_ids = [r.run_id for r in listed]
        # The three just-saved runs must appear newest-first.
        positions = [listed_ids.index(rid) for rid in reversed(run_ids)]
        assert positions == sorted(positions), f"not newest-first: {listed_ids}"
    finally:
        for rid in run_ids:
            repo.delete(rid)


@needs_postgres
def test_postgres_repository_rejects_duplicate_run_id(clean_trace, agent_config, test_case):
    from tests.test_reporting_history import generate_report_with_run_id

    repo = PostgresReportRepository()
    dup_id = _unique_run_id("run_pg_dup")
    report = generate_report_with_run_id(dup_id, clean_trace, agent_config, test_case)
    try:
        repo.save(report)
        with pytest.raises(ValueError, match="already exists"):
            repo.save(report)
        assert repo.get(dup_id) is not None
    finally:
        repo.delete(dup_id)
