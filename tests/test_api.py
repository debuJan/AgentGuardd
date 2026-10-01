import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api import deps as api_deps
from src.core.trace import ExecutionTrace, ToolCallEvent, ToolResultEvent, FinalResponseEvent

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolated_memory_repository(monkeypatch):
    """Run API tests against a fresh in-memory repository (no Postgres needed)."""
    monkeypatch.setenv("USE_POSTGRES", "false")
    api_deps.reset_repository()
    yield
    api_deps.reset_repository()


# 1. GET /health succeeds
def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


# 2. POST /runs creates and stores report, and GET /runs/{run_id} retrieves it
def test_post_runs_and_get_by_id(clean_trace, agent_config, test_case):
    clean_trace.run_id = "api_run_001"

    payload = {
        "agent_config": agent_config.model_dump() if hasattr(agent_config, "model_dump") else agent_config.dict(),
        "test_case": test_case.model_dump() if hasattr(test_case, "model_dump") else test_case.dict(),
        "trace": clean_trace.model_dump() if hasattr(clean_trace, "model_dump") else clean_trace.dict(),
    }

    res = client.post("/runs", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["run_id"] == "api_run_001"

    # Get by ID
    get_res = client.get("/runs/api_run_001")
    assert get_res.status_code == 200
    assert get_res.json()["run_id"] == "api_run_001"


# 3. GET /runs/{run_id} returns 404 for unknown run
def test_get_run_404_for_unknown_id():
    res = client.get("/runs/non_existent_id")
    assert res.status_code == 404


# 4. GET /runs lists reports
def test_list_runs(clean_trace, agent_config, test_case):
    # Post two runs
    for run_id in ["run_a", "run_b"]:
        clean_trace.run_id = run_id
        payload = {
            "agent_config": agent_config.model_dump() if hasattr(agent_config, "model_dump") else agent_config.dict(),
            "test_case": test_case.model_dump() if hasattr(test_case, "model_dump") else test_case.dict(),
            "trace": clean_trace.model_dump() if hasattr(clean_trace, "model_dump") else clean_trace.dict(),
        }
        client.post("/runs", json=payload)

    res = client.get("/runs")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 2
    assert len(data["reports"]) == 2


# 5. GET /runs supports agent_id filtering
# 6. GET /runs supports test_case_id filtering
def test_list_runs_filtering(clean_trace, agent_config, test_case):
    clean_trace.run_id = "run_filter_1"
    payload = {
        "agent_config": agent_config.model_dump() if hasattr(agent_config, "model_dump") else agent_config.dict(),
        "test_case": test_case.model_dump() if hasattr(test_case, "model_dump") else test_case.dict(),
        "trace": clean_trace.model_dump() if hasattr(clean_trace, "model_dump") else clean_trace.dict(),
    }
    created_res = client.post("/runs", json=payload).json()

    agent_id = created_res["agent_id"]
    tc_id = created_res["test_case_id"]

    res_agent = client.get(f"/runs?agent_id={agent_id}")
    assert res_agent.status_code == 200
    assert len(res_agent.json()["reports"]) >= 1

    res_tc = client.get(f"/runs?test_case_id={tc_id}")
    assert res_tc.status_code == 200
    assert len(res_tc.json()["reports"]) >= 1


# 7. GET /runs respects limit
def test_list_runs_limit(clean_trace, agent_config, test_case):
    for i in range(4):
        clean_trace.run_id = f"limit_run_{i}"
        payload = {
            "agent_config": agent_config.model_dump() if hasattr(agent_config, "model_dump") else agent_config.dict(),
            "test_case": test_case.model_dump() if hasattr(test_case, "model_dump") else test_case.dict(),
            "trace": clean_trace.model_dump() if hasattr(clean_trace, "model_dump") else clean_trace.dict(),
        }
        client.post("/runs", json=payload)

    res = client.get("/runs?limit=2")
    assert res.status_code == 200
    assert len(res.json()["reports"]) == 2


# 8. DELETE /runs/{run_id} deletes report
def test_delete_run(clean_trace, agent_config, test_case):
    clean_trace.run_id = "delete_target"
    payload = {
        "agent_config": agent_config.model_dump() if hasattr(agent_config, "model_dump") else agent_config.dict(),
        "test_case": test_case.model_dump() if hasattr(test_case, "model_dump") else test_case.dict(),
        "trace": clean_trace.model_dump() if hasattr(clean_trace, "model_dump") else clean_trace.dict(),
    }
    client.post("/runs", json=payload)

    del_res = client.delete("/runs/delete_target")
    assert del_res.status_code == 200

    get_res = client.get("/runs/delete_target")
    assert get_res.status_code == 404


# 9. DELETE unknown run returns 404
def test_delete_unknown_run_404():
    res = client.delete("/runs/unknown_run")
    assert res.status_code == 404


# 10. API integration preserves underlying reporting functionality
def test_api_does_not_break_existing_reporting(clean_trace, agent_config, test_case):
    clean_trace.run_id = "preservation_run"
    payload = {
        "agent_config": agent_config.model_dump() if hasattr(agent_config, "model_dump") else agent_config.dict(),
        "test_case": test_case.model_dump() if hasattr(test_case, "model_dump") else test_case.dict(),
        "trace": clean_trace.model_dump() if hasattr(clean_trace, "model_dump") else clean_trace.dict(),
    }
    res = client.post("/runs", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "overall_score" in data
    assert "overall_status" in data
    assert "reliability" in data
    assert "security" in data
    assert "metrics" in data

def test_api_policy_violation_is_reported(clean_trace, agent_config, test_case):
        clean_trace.run_id = "api_policy_violation"

        # Deliberately violate the configured policy:
        # issue_refund must happen AFTER get_order.
        trace = ExecutionTrace(
            run_id="api_policy_violation",
            agent_id=clean_trace.agent_id,
            test_case_id=clean_trace.test_case_id,
            steps=[],
        )

        trace.add_event(
            ToolCallEvent(
                tool_name="issue_refund",
                arguments={"order_id": 1234},
            )
        )
        trace.add_event(
            ToolResultEvent(
                tool_name="issue_refund",
                result={"status": "success"},
            )
        )
        trace.add_event(
            ToolCallEvent(
                tool_name="check_refund_eligibility",
                arguments={"order_id": 1234},
            )
        )
        trace.add_event(
            ToolResultEvent(
                tool_name="check_refund_eligibility",
                result={"eligible": True},
            )
        )
        trace.add_event(FinalResponseEvent(content="Refunded."))
        trace.mark_complete(final_response="Refunded.")

        payload = {
            "agent_config": (
                agent_config.model_dump()
                if hasattr(agent_config, "model_dump")
                else agent_config.dict()
            ),
            "test_case": (
                test_case.model_dump()
                if hasattr(test_case, "model_dump")
                else test_case.dict()
            ),
            "trace": (
                trace.model_dump()
                if hasattr(trace, "model_dump")
                else trace.dict()
            ),
        }

        response = client.post("/runs", json=payload)

        assert response.status_code == 201

        report = response.json()

        assert report["overall_status"] != "PASS"
        assert report["security"]["passed"] is False

        categories = [
            finding["category"]
            for finding in report["security"]["findings"]
        ]

        assert "policy_violation" in categories


# 11. POST /runs with an unknown LLM provider is a 400, not a 500
def test_post_runs_unknown_provider_is_400(agent_config, test_case):
    agent_config.llm.provider = "nonexistent_provider"
    payload = {
        "agent_config": agent_config.model_dump(),
        "test_case": test_case.model_dump(),
    }
    res = client.post("/runs", json=payload)
    assert res.status_code == 400
    assert "provider" in res.json()["detail"].lower()


# 12. GET /runs rejects a non-positive limit with 400
def test_list_runs_rejects_bad_limit():
    res = client.get("/runs?limit=0")
    assert res.status_code == 400


# 13. Repository outage surfaces as 503, not a crash
def test_repository_outage_is_503(monkeypatch):
    def _boom():
        raise ConnectionError("db down")

    monkeypatch.setattr(api_deps, "_create_repository", _boom)
    api_deps.reset_repository()

    res = client.get("/runs")
    assert res.status_code == 503

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["database"] == "unavailable"

# 14. API-key auth: enforced only when AGENTGUARD_API_KEY is configured
def test_api_key_auth_enforced_when_configured(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_API_KEY", "test-secret-key")

    # No key -> 401
    res = client.get("/runs")
    assert res.status_code == 401

    # Wrong key -> 401
    res = client.get("/runs", headers={"X-API-Key": "wrong"})
    assert res.status_code == 401

    # Right key -> through
    res = client.get("/runs", headers={"X-API-Key": "test-secret-key"})
    assert res.status_code == 200

    # /health stays open
    res = client.get("/health")
    assert res.status_code == 200


def test_api_key_auth_disabled_when_not_configured(monkeypatch):
    monkeypatch.delenv("AGENTGUARD_API_KEY", raising=False)
    res = client.get("/runs")
    assert res.status_code == 200


# 15. Duplicate run_id via API -> 409 Conflict (not 500)
def test_post_runs_duplicate_run_id_returns_409(clean_trace, agent_config, test_case):
    clean_trace.run_id = "api_run_dup_001"

    def dump(m):
        return m.model_dump() if hasattr(m, "model_dump") else m.dict()

    payload = {
        "agent_config": dump(agent_config),
        "test_case": dump(test_case),
        "trace": dump(clean_trace),
    }

    first = client.post("/runs", json=payload)
    assert first.status_code == 201

    second = client.post("/runs", json=payload)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]
