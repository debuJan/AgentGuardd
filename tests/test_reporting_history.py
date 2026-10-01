import pytest

from src.reporting.engine import ReportingEngine
from src.reporting.history.memory import InMemoryReportRepository


# --- Helper Function ---

def generate_report_with_run_id(run_id: str, clean_trace, agent_config, test_case, repository=None):
    """Helper to mutate trace.run_id and generate a report using the existing Phase 6 pattern."""
    clean_trace.run_id = run_id
    engine = ReportingEngine(repository=repository)
    return engine.generate(clean_trace, agent_config, test_case)


# --- Tests ---

# 1. Save and retrieve a report.
def test_save_and_retrieve_report(clean_trace, agent_config, test_case):
    repo = InMemoryReportRepository()
    report = generate_report_with_run_id("run_100", clean_trace, agent_config, test_case)
    repo.save(report)

    retrieved = repo.get("run_100")
    assert retrieved is not None
    assert retrieved.run_id == "run_100"


# 2. Unknown run_id returns None.
def test_get_unknown_run_id_returns_none():
    repo = InMemoryReportRepository()
    assert repo.get("non_existent_run_id") is None


# 3. List all reports.
def test_list_all_reports(clean_trace, agent_config, test_case):
    repo = InMemoryReportRepository()
    r1 = generate_report_with_run_id("run_1", clean_trace, agent_config, test_case)
    r2 = generate_report_with_run_id("run_2", clean_trace, agent_config, test_case)
    repo.save(r1)
    repo.save(r2)

    runs = repo.list_runs()
    assert len(runs) == 2
    # Newest first (deterministic ordering).
    assert [r.run_id for r in runs] == ["run_2", "run_1"]


# 4. Filter by agent_id.
def test_filter_by_agent_id(clean_trace, agent_config, test_case):
    repo = InMemoryReportRepository()
    r1 = generate_report_with_run_id("run_1", clean_trace, agent_config, test_case)
    repo.save(r1)

    target_agent_id = r1.agent_id
    filtered = repo.list_runs(agent_id=target_agent_id)
    assert len(filtered) >= 1
    assert all(r.agent_id == target_agent_id for r in filtered)


# 5. Filter by test_case_id.
def test_filter_by_test_case_id(clean_trace, agent_config, test_case):
    repo = InMemoryReportRepository()
    r1 = generate_report_with_run_id("run_1", clean_trace, agent_config, test_case)
    repo.save(r1)

    target_tc_id = r1.test_case_id
    filtered = repo.list_runs(test_case_id=target_tc_id)
    assert len(filtered) == 1
    assert filtered[0].test_case_id == target_tc_id


# 6. Limit returned reports.
def test_limit_returned_reports(clean_trace, agent_config, test_case):
    repo = InMemoryReportRepository()
    for i in range(5):
        repo.save(generate_report_with_run_id(f"run_limit_{i}", clean_trace, agent_config, test_case))

    runs = repo.list_runs(limit=3)
    assert len(runs) == 3
    # Newest first: the limit keeps the three most recent runs.
    assert [r.run_id for r in runs] == ["run_limit_4", "run_limit_3", "run_limit_2"]


# 7. Delete an existing report.
def test_delete_existing_report(clean_trace, agent_config, test_case):
    repo = InMemoryReportRepository()
    report = generate_report_with_run_id("run_del", clean_trace, agent_config, test_case)
    repo.save(report)

    deleted = repo.delete("run_del")
    assert deleted is True
    assert repo.get("run_del") is None


# 8. Delete a non-existing report returns False.
def test_delete_non_existing_report_returns_false():
    repo = InMemoryReportRepository()
    assert repo.delete("missing_run") is False


# 9. Saving the same run_id replaces the existing report.
# 10. No duplicate report exists after replacement.
def test_save_same_run_id_is_rejected(clean_trace, agent_config, test_case):
    repo = InMemoryReportRepository()
    r1 = generate_report_with_run_id("run_dup", clean_trace, agent_config, test_case)
    r2 = generate_report_with_run_id("run_dup", clean_trace, agent_config, test_case)

    repo.save(r1)
    with pytest.raises(ValueError, match="already exists"):
        repo.save(r2)

    # The original report is untouched.
    assert repo.get("run_dup") is not None
    assert len(repo.list_runs()) == 1


# 11. Stored report remains unchanged after storing.
def test_reports_remain_unchanged_after_storing(clean_trace, agent_config, test_case):
    repo = InMemoryReportRepository()
    report = generate_report_with_run_id("run_static", clean_trace, agent_config, test_case)
    original_score = report.overall_score

    repo.save(report)
    retrieved = repo.get("run_static")

    assert retrieved is not None
    assert retrieved.overall_score == original_score


# 12. ReportingEngine saves generated reports when a repository is supplied.
def test_reporting_engine_saves_when_repository_supplied(clean_trace, agent_config, test_case):
    repo = InMemoryReportRepository()
    engine = ReportingEngine(repository=repo)

    clean_trace.run_id = "run_repo_supplied"
    report = engine.generate(clean_trace, agent_config, test_case)
    saved_report = repo.get(report.run_id)

    assert saved_report is not None
    assert saved_report.run_id == report.run_id


# 13. ReportingEngine still works normally when no repository is supplied.
def test_reporting_engine_works_without_repository(clean_trace, agent_config, test_case):
    engine = ReportingEngine()
    report = engine.generate(clean_trace, agent_config, test_case)

    assert report is not None


# 14. Invalid limit raises ValueError.
def test_invalid_limit_raises_value_error():
    repo = InMemoryReportRepository()
    with pytest.raises(ValueError):
        repo.list_runs(limit=0)

    with pytest.raises(ValueError):
        repo.list_runs(limit=-1)