import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from src.core.agent_runner import AgentRunner
from src.core.config_models import TestCase
from src.core.llm_provider import get_llm_provider

from src.api.auth import require_api_key
from src.api.deps import get_repository, get_reporting_engine, get_test_case_repository
from src.api.schemas import (
    HealthResponse,
    RunExecutionRequest,
    RunReportListResponse,
    TestCaseCreate,
    TestCaseListResponse,
)
from src.reporting.engine import ReportingEngine
from src.reporting.history.repository import ReportRepository, TestCaseRepository
from src.reporting.models import UnifiedRunReport

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_LIST_LIMIT = 100


def _resolve_test_case(req: RunExecutionRequest) -> TestCase:
    """Return the run's test case from an inline object or a library id.

    Exactly one of ``test_case`` / ``test_case_id`` must be provided.
    The library is only touched when ``test_case_id`` is used, so inline
    runs keep working even if the test-case store is unreachable.
    """
    if req.test_case is None and req.test_case_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either 'test_case' or 'test_case_id'.",
        )
    if req.test_case is not None and req.test_case_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide only one of 'test_case' or 'test_case_id'.",
        )
    if req.test_case is not None:
        return req.test_case
    repo = get_test_case_repository()
    test_case = repo.get(req.test_case_id)
    if test_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{req.test_case_id}' not found.",
        )
    return test_case


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check: API liveness plus report-store reachability.

    Never fails because of the database: an unreachable store is reported
    as ``database="unavailable"`` so orchestrators can see the API is up
    but degraded.
    """
    try:
        repo = get_repository()
    except HTTPException:
        return HealthResponse(status="ok", database="unavailable")
    try:
        repo.list_runs(limit=1)
        database = "ok"
    except Exception as exc:  # noqa: BLE001 - health must not crash
        logger.warning("Health check: repository unreachable: %s", exc)
        database = "unavailable"
    return HealthResponse(status="ok", database=database)


@router.post("/runs", response_model=UnifiedRunReport, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_run_report(
    req: RunExecutionRequest,
    engine: ReportingEngine = Depends(get_reporting_engine),
):
    """
    Executes the configured agent against the test case and generates
    a unified reliability, security, and observability report.
    """

    # Resolve the test case: inline object or library reference (not both).
    test_case = _resolve_test_case(req)

    # Use an existing trace if one was explicitly supplied.
    if req.trace is not None:
        trace = req.trace
    else:
        # External agents do not need AgentGuard's LLM provider.
        provider = None

        if req.agent_config.execution_type != "external":
            try:
                provider = get_llm_provider(
                    provider=req.agent_config.llm.provider,
                    model_name=req.agent_config.llm.model,
                    temperature=req.agent_config.llm.temperature,
                    max_tokens=req.agent_config.llm.max_tokens,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                )

        # Execute the actual agent.
        runner = AgentRunner(
            agent_config=req.agent_config,
            llm_provider=provider,
        )

        try:
            trace = runner.run(test_case)
        except Exception as exc:  # noqa: BLE001 - mapped to 500 below
            logger.exception("Agent run failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent execution failed: {exc}",
            )

    # Generate the unified report.
    try:
        report = engine.generate(
            trace=trace,
            agent_config=req.agent_config,
            test_case=test_case,
        )
    except ValueError as exc:
        # Client error, e.g. a report with this run_id already exists.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except Exception:  # noqa: BLE001 - mapped to 500 below
        logger.exception("Report generation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report generation failed due to an internal error.",
        )

    return report


@router.get("/runs/{run_id}", response_model=UnifiedRunReport, dependencies=[Depends(require_api_key)])
def get_run_report(
    run_id: str,
    repo: ReportRepository = Depends(get_repository),
):
    """Retrieve a stored UnifiedRunReport from the ReportRepository."""
    report = repo.get(run_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with run_id '{run_id}' not found.",
        )
    return report


@router.get("/runs", response_model=RunReportListResponse, dependencies=[Depends(require_api_key)])
def list_run_reports(
    agent_id: Optional[str] = Query(None),
    test_case_id: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    repo: ReportRepository = Depends(get_repository),
):
    """List reports stored in the repository with optional filtering and limits."""
    if limit is not None and limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be a positive integer.",
        )
    try:
        kwargs = {}
        if agent_id is not None:
            kwargs["agent_id"] = agent_id
        if test_case_id is not None:
            kwargs["test_case_id"] = test_case_id
        kwargs["limit"] = min(limit, MAX_LIST_LIMIT) if limit is not None else MAX_LIST_LIMIT

        reports = repo.list_runs(**kwargs)
        return RunReportListResponse(reports=reports, count=len(reports))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.delete("/runs/{run_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(require_api_key)])
def delete_run_report(
    run_id: str,
    repo: ReportRepository = Depends(get_repository),
):
    """Delete a report from the repository by run_id."""
    success = repo.delete(run_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with run_id '{run_id}' not found.",
        )
    return {"message": f"Report '{run_id}' deleted successfully."}


# ---------------------------------------------------------------------
# Test-case library
# ---------------------------------------------------------------------

@router.post("/test-cases", response_model=TestCase, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_test_case(
    payload: TestCaseCreate,
    repo: TestCaseRepository = Depends(get_test_case_repository),
):
    """Author a reusable test case in the library.

    The ``id`` is optional: when omitted the server assigns ``tc_<uuid8>``.
    Duplicate ids are rejected with 409.
    """
    test_case_id = payload.id.strip() if payload.id else ""
    if not test_case_id:
        test_case_id = f"tc_{uuid.uuid4().hex[:8]}"
    test_case = payload.to_test_case(test_case_id)
    try:
        repo.save(test_case)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return test_case


@router.get("/test-cases", response_model=TestCaseListResponse, dependencies=[Depends(require_api_key)])
def list_test_cases(
    category: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    repo: TestCaseRepository = Depends(get_test_case_repository),
):
    """List stored test cases, newest first, with optional category filter."""
    if limit is not None and limit < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be a positive integer.",
        )
    try:
        cases = repo.list(
            category=category,
            limit=min(limit, MAX_LIST_LIMIT) if limit is not None else MAX_LIST_LIMIT,
        )
        return TestCaseListResponse(test_cases=cases, count=len(cases))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/test-cases/{test_case_id}", response_model=TestCase, dependencies=[Depends(require_api_key)])
def get_test_case(
    test_case_id: str,
    repo: TestCaseRepository = Depends(get_test_case_repository),
):
    """Retrieve a single test case from the library."""
    test_case = repo.get(test_case_id)
    if test_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{test_case_id}' not found.",
        )
    return test_case


@router.delete("/test-cases/{test_case_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(require_api_key)])
def delete_test_case(
    test_case_id: str,
    repo: TestCaseRepository = Depends(get_test_case_repository),
):
    """Delete a test case from the library."""
    success = repo.delete(test_case_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test case '{test_case_id}' not found.",
        )
    return {"message": f"Test case '{test_case_id}' deleted successfully."}
