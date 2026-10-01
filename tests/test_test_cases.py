"""Tests for the reusable test-case library.

Covers the /test-cases CRUD API, test_case_id resolution in POST /runs,
and both repository backends (in-memory + Postgres/SQLite).
"""
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api import deps as api_deps
from src.core.config_models import TestCase, TestCaseCategory
from src.reporting.history.memory import InMemoryTestCaseRepository
from src.reporting.history.postgres import PostgresTestCaseRepository, TestCaseRow

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def isolated_memory_repositories(monkeypatch):
    """Run API tests against fresh in-memory repositories (no Postgres needed)."""
    monkeypatch.setenv("USE_POSTGRES", "false")
    api_deps.reset_repository()
    yield
    api_deps.reset_repository()


def _case_payload(**overrides):
    payload = {
        "title": "Refund - Happy Path",
        "agent_name": "ecommerce_refund_agent",
        "category": "reliability",
        "user_input": "Refund order #1234.",
        "expected_tool_calls": [
            {"tool": "get_order", "order": 1},
            {"tool": "check_refund_eligibility", "order": 2},
            {"tool": "issue_refund", "order": 3},
        ],
        "expected_outcome": "Order refunded successfully.",
    }
    payload.update(overrides)
    return payload


# --- CRUD API ---------------------------------------------------------

def test_create_test_case_with_explicit_id():
    res = client.post("/test-cases", json=_case_payload(id="tc_demo_1"))
    assert res.status_code == 201
    body = res.json()
    assert body["id"] == "tc_demo_1"
    assert body["title"] == "Refund - Happy Path"
    assert body["category"] == "reliability"
    assert len(body["expected_tool_calls"]) == 3


def test_create_test_case_assigns_id_when_omitted():
    res = client.post("/test-cases", json=_case_payload())
    assert res.status_code == 201
    body = res.json()
    assert body["id"].startswith("tc_")
    assert len(body["id"]) > 3


def test_create_duplicate_id_conflicts():
    assert client.post("/test-cases", json=_case_payload(id="tc_dup")).status_code == 201
    res = client.post("/test-cases", json=_case_payload(id="tc_dup"))
    assert res.status_code == 409


def test_get_test_case_by_id():
    client.post("/test-cases", json=_case_payload(id="tc_get_me"))
    res = client.get("/test-cases/tc_get_me")
    assert res.status_code == 200
    assert res.json()["user_input"] == "Refund order #1234."


def test_get_unknown_test_case_404():
    assert client.get("/test-cases/nope").status_code == 404


def test_list_test_cases_newest_first_and_category_filter():
    client.post("/test-cases", json=_case_payload(id="tc_first", category="reliability"))
    client.post("/test-cases", json=_case_payload(id="tc_second", category="security"))

    res = client.get("/test-cases")
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 2
    # Newest first.
    assert [c["id"] for c in body["test_cases"]] == ["tc_second", "tc_first"]

    res = client.get("/test-cases", params={"category": "security"})
    assert res.status_code == 200
    body = res.json()
    assert body["count"] == 1
    assert body["test_cases"][0]["id"] == "tc_second"


def test_list_test_cases_limit_validation():
    assert client.get("/test-cases", params={"limit": 0}).status_code == 400


def test_delete_test_case():
    client.post("/test-cases", json=_case_payload(id="tc_gone"))
    res = client.delete("/test-cases/tc_gone")
    assert res.status_code == 200
    assert client.get("/test-cases/tc_gone").status_code == 404
    # Second delete -> 404.
    assert client.delete("/test-cases/tc_gone").status_code == 404


# --- POST /runs integration -------------------------------------------

def _run_payload(agent_config, trace, **overrides):
    payload = {
        "agent_config": agent_config.model_dump(),
        "trace": trace.model_dump(),
    }
    payload.update(overrides)
    return payload


def test_run_with_test_case_id(agent_config, clean_trace):
    client.post("/test-cases", json=_case_payload(id="tc_lib_1"))
    clean_trace.run_id = "run_via_lib_1"
    payload = _run_payload(agent_config, clean_trace, test_case_id="tc_lib_1")

    res = client.post("/runs", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["run_id"] == "run_via_lib_1"
    assert body["test_case_id"] == "tc_lib_1"


def test_run_with_unknown_test_case_id_404(agent_config, clean_trace, test_case):
    clean_trace.run_id = "run_via_lib_404"
    payload = _run_payload(
        agent_config, clean_trace, test_case_id="tc_missing"
    )
    res = client.post("/runs", json=payload)
    assert res.status_code == 404


def test_run_with_neither_test_case_nor_id_400(agent_config, clean_trace):
    clean_trace.run_id = "run_via_lib_400"
    payload = _run_payload(agent_config, clean_trace)
    res = client.post("/runs", json=payload)
    assert res.status_code == 400


def test_run_with_both_test_case_and_id_400(agent_config, clean_trace, test_case):
    client.post("/test-cases", json=_case_payload(id="tc_lib_both"))
    clean_trace.run_id = "run_via_lib_both"
    payload = _run_payload(
        agent_config,
        clean_trace,
        test_case=test_case.model_dump(),
        test_case_id="tc_lib_both",
    )
    res = client.post("/runs", json=payload)
    assert res.status_code == 400


def test_run_with_inline_test_case_still_works(agent_config, clean_trace, test_case):
    """Backward compatibility: the pre-library inline payload is unchanged."""
    clean_trace.run_id = "run_inline_still_ok"
    payload = _run_payload(
        agent_config, clean_trace, test_case=test_case.model_dump()
    )
    res = client.post("/runs", json=payload)
    assert res.status_code == 201


# --- Repository backends ----------------------------------------------

def _sample_case(case_id="tc_repo_1"):
    return TestCase(
        id=case_id,
        title="Sample",
        agent_name="agent_x",
        category=TestCaseCategory.SECURITY,
        user_input="Do something shady.",
        expected_outcome="Refused.",
    )


def test_memory_repository_crud():
    repo = InMemoryTestCaseRepository()
    repo.save(_sample_case("a"))
    repo.save(_sample_case("b"))

    assert repo.get("a").title == "Sample"
    assert repo.get("missing") is None

    listed = repo.list()
    assert [c.id for c in listed] == ["b", "a"]  # newest first
    assert [c.id for c in repo.list(category="security")] == ["b", "a"]
    assert repo.list(category="reliability") == []

    with pytest.raises(ValueError):
        repo.save(_sample_case("a"))
    with pytest.raises(ValueError):
        repo.list(limit=0)

    assert repo.delete("a") is True
    assert repo.delete("a") is False
    assert repo.get("a") is None


def test_postgres_repository_crud(tmp_path):
    from datetime import datetime, timezone
    from sqlalchemy import update

    repo = PostgresTestCaseRepository(f"sqlite:///{tmp_path}/tc.db")
    repo.save(_sample_case("a"))
    repo.save(_sample_case("b"))
    # SQLite timestamps have 1-second precision, so force distinct
    # created_at values to exercise newest-first ordering deterministically.
    with repo.engine.begin() as conn:
        conn.execute(
            update(TestCaseRow)
            .where(TestCaseRow.id == "a")
            .values(created_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
        )

    fetched = repo.get("a")
    assert fetched is not None
    assert fetched.title == "Sample"
    assert fetched.category == TestCaseCategory.SECURITY
    assert fetched.user_input == "Do something shady."
    assert repo.get("missing") is None

    listed = repo.list()
    assert [c.id for c in listed] == ["b", "a"]  # newest first
    assert [c.id for c in repo.list(category="security")] == ["b", "a"]
    assert repo.list(category="reliability") == []

    with pytest.raises(ValueError):
        repo.save(_sample_case("a"))
    with pytest.raises(ValueError):
        repo.list(limit=0)

    assert repo.delete("a") is True
    assert repo.delete("a") is False
    assert repo.get("a") is None
