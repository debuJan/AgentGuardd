from typing import List, Optional

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, create_engine, func, select, text
from sqlalchemy.orm import DeclarativeBase, Session

from src.core.config_models import TestCase
from src.core.trace import ExecutionTrace
from src.db import DATABASE_URL
from src.reporting.history.repository import ReportRepository, TestCaseRepository
from src.reporting.models import UnifiedRunReport


class Base(DeclarativeBase):
    pass


class RunReportRow(Base):
    __tablename__ = "run_reports"

    run_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False, index=True)
    test_case_id = Column(String, nullable=False, index=True)
    overall_status = Column(String, nullable=False)
    overall_score = Column(Float, nullable=False)

    reliability = Column(JSON, nullable=False)
    security = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=False)

    # Complete execution trace
    trace = Column(JSON, nullable=True)

    duration_ms = Column(Float, default=0.0)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)

    llm_call_count = Column(Integer, default=0)
    tool_call_count = Column(Integer, default=0)
    tool_error_count = Column(Integer, default=0)
    repeated_tool_call_count = Column(Integer, default=0)

    important_failures = Column(JSON, nullable=False, default=list)
    metadata_json = Column(JSON, nullable=False, default=dict)

    # Newest-first listing needs a timestamp; backfilled for pre-existing rows.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PostgresReportRepository(ReportRepository):
    def __init__(self, database_url: str = DATABASE_URL) -> None:
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
        )

        Base.metadata.create_all(self.engine)
        # Idempotent mini-migration for databases created before the
        # created_at column existed (create_all never alters tables).
        # A full Alembic migration setup is the recommended next step.
        with Session(self.engine) as session:
            try:
                session.execute(
                    text(
                        "ALTER TABLE run_reports "
                        "ADD COLUMN IF NOT EXISTS created_at "
                        "TIMESTAMPTZ DEFAULT now()"
                    )
                )
                session.commit()
            except Exception:
                session.rollback()

    def save(self, report: UnifiedRunReport) -> None:
        with Session(self.engine) as session:
            existing = session.get(RunReportRow, report.run_id)
            if existing is not None:
                raise ValueError(
                    f"Report with run_id '{report.run_id}' already exists."
                )
            row = RunReportRow(
                run_id=report.run_id,
                agent_id=report.agent_id,
                test_case_id=report.test_case_id,
                overall_status=report.overall_status.value,
                overall_score=report.overall_score,
                reliability=report.reliability.model_dump(mode="json"),
                security=report.security.model_dump(mode="json"),
                metrics=report.metrics.model_dump(mode="json"),
                trace=(
                    report.trace.model_dump(mode="json")
                    if report.trace
                    else None
                ),
                duration_ms=report.duration_ms,
                total_tokens=report.total_tokens,
                estimated_cost_usd=report.estimated_cost_usd,
                llm_call_count=report.llm_call_count,
                tool_call_count=report.tool_call_count,
                tool_error_count=report.tool_error_count,
                repeated_tool_call_count=report.repeated_tool_call_count,
                important_failures=report.important_failures,
                metadata_json=report.metadata,
                # created_at intentionally unset: the column's server_default
                # stamps true creation time exactly once.
            )

            session.add(row)
            session.commit()

    def get(self, run_id: str) -> Optional[UnifiedRunReport]:
        with Session(self.engine) as session:
            row = session.get(RunReportRow, run_id)

            if row is None:
                return None

            return self._to_report(row)

    def list_runs(
        self,
        agent_id: Optional[str] = None,
        test_case_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[UnifiedRunReport]:

        if limit < 1:
            raise ValueError("Limit must be greater than or equal to 1.")

        with Session(self.engine) as session:
            query = select(RunReportRow)

            if agent_id is not None:
                query = query.where(RunReportRow.agent_id == agent_id)

            if test_case_id is not None:
                query = query.where(RunReportRow.test_case_id == test_case_id)

            query = query.limit(limit)

            # Deterministic newest-first ordering (run_id tiebreak).
            query = query.order_by(
                RunReportRow.created_at.desc(), RunReportRow.run_id.asc()
            )

            rows = session.execute(query).scalars().all()

            return [self._to_report(row) for row in rows]

    def delete(self, run_id: str) -> bool:
        with Session(self.engine) as session:
            row = session.get(RunReportRow, run_id)

            if row is None:
                return False

            session.delete(row)
            session.commit()

            return True

    @staticmethod
    def _to_report(row: RunReportRow) -> UnifiedRunReport:
        return UnifiedRunReport(
            run_id=row.run_id,
            agent_id=row.agent_id,
            test_case_id=row.test_case_id,
            overall_status=row.overall_status,
            overall_score=row.overall_score,
            reliability=row.reliability,
            security=row.security,
            metrics=row.metrics,
            trace=(
                ExecutionTrace.model_validate(row.trace)
                if row.trace
                else None
            ),
            duration_ms=row.duration_ms,
            total_tokens=row.total_tokens,
            estimated_cost_usd=row.estimated_cost_usd,
            llm_call_count=row.llm_call_count,
            tool_call_count=row.tool_call_count,
            tool_error_count=row.tool_error_count,
            repeated_tool_call_count=row.repeated_tool_call_count,
            important_failures=row.important_failures or [],
            metadata=row.metadata_json or {},
        )

class TestCaseRow(Base):
    """Persistent row for the reusable test-case library."""

    __tablename__ = "test_cases"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=True)
    agent_name = Column(String, nullable=False, default="")
    category = Column(String, nullable=False, index=True)
    user_input = Column(Text, nullable=False)
    expected_tool_calls = Column(JSON, nullable=False, default=list)
    expected_outcome = Column(Text, nullable=True)
    security_expectation = Column(JSON, nullable=False, default=dict)
    max_tool_calls = Column(Integer, nullable=True)
    max_latency_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PostgresTestCaseRepository(TestCaseRepository):
    """Postgres-backed test-case library."""

    def __init__(self, database_url: str = DATABASE_URL) -> None:
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
        )
        # Creates test_cases (and any other missing tables) idempotently.
        Base.metadata.create_all(self.engine)

    def save(self, test_case: TestCase) -> None:
        with Session(self.engine) as session:
            existing = session.get(TestCaseRow, test_case.id)
            if existing is not None:
                raise ValueError(
                    f"Test case with id '{test_case.id}' already exists."
                )
            row = TestCaseRow(
                id=test_case.id,
                title=test_case.title,
                agent_name=test_case.agent_name,
                category=test_case.category.value,
                user_input=test_case.user_input,
                expected_tool_calls=[
                    c.model_dump(mode="json") for c in test_case.expected_tool_calls
                ],
                expected_outcome=test_case.expected_outcome,
                security_expectation=test_case.security_expectation.model_dump(
                    mode="json"
                ),
                max_tool_calls=test_case.max_tool_calls,
                max_latency_ms=test_case.max_latency_ms,
                # created_at/updated_at intentionally unset: server defaults
                # stamp them exactly once.
            )
            session.add(row)
            session.commit()

    def get(self, test_case_id: str) -> Optional[TestCase]:
        with Session(self.engine) as session:
            row = session.get(TestCaseRow, test_case_id)
            if row is None:
                return None
            return self._to_test_case(row)

    def list(
        self,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[TestCase]:
        if limit < 1:
            raise ValueError("Limit must be greater than or equal to 1.")

        with Session(self.engine) as session:
            query = select(TestCaseRow)
            if category is not None:
                query = query.where(TestCaseRow.category == category)
            query = query.limit(limit)
            # Deterministic newest-first ordering (id tiebreak).
            query = query.order_by(
                TestCaseRow.created_at.desc(), TestCaseRow.id.asc()
            )
            rows = session.execute(query).scalars().all()
            return [self._to_test_case(row) for row in rows]

    def delete(self, test_case_id: str) -> bool:
        with Session(self.engine) as session:
            row = session.get(TestCaseRow, test_case_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    @staticmethod
    def _to_test_case(row: TestCaseRow) -> TestCase:
        return TestCase.model_validate(
            {
                "id": row.id,
                "title": row.title,
                "agent_name": row.agent_name or "",
                "category": row.category,
                "user_input": row.user_input,
                "expected_tool_calls": row.expected_tool_calls or [],
                "expected_outcome": row.expected_outcome,
                "security_expectation": row.security_expectation or {},
                "max_tool_calls": row.max_tool_calls,
                "max_latency_ms": row.max_latency_ms,
            }
        )
