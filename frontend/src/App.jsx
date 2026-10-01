import React, { useState, useEffect, useCallback } from 'react';
import { api } from './api/client';
import DashboardOverview from './components/DashboardOverview';
import FilterBar from './components/FilterBar';
import RunHistoryTable from './components/RunHistoryTable';
import RunDetailView from './components/RunDetailView';
import AgentsView from './components/AgentsView';
import LoadingSpinner from './components/common/LoadingSpinner';
import TestCasesView from './components/TestCasesView';
import ErrorAlert from './components/common/ErrorAlert';
import Sidebar from './components/Sidebar';
import AlertsView from './components/AlertsView';
import SettingsView from './components/SettingsView';
import {
  getDurationMs,
  getTotalCostUsd,
  getTotalTokens,
  isPassStatus,
} from './utils/reportFields';
import './dashboard.css';

/**
 * Severity -> display risk mapping. The severity comes from the backend
 * security engine; this only converts it to a 0-100 display scale.
 */
const SEVERITY_RISK = {
  CRITICAL: 100,
  HIGH: 80,
  MEDIUM: 60,
  LOW: 40,
};

/**
 * App Component
 * Main entry point for the AI Agent Reliability & Security Platform Dashboard.
 */
export function App() {
  const [currentView, setCurrentView] = useState('dashboard');
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [filters, setFilters] = useState({ agent_id: '', test_case_id: '', limit: '' });

  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);
  const [healthStatus, setHealthStatus] = useState('checking');

  // Check API health on initial mount
  useEffect(() => {
    api
      .checkHealth()
      .then(() => setHealthStatus('ok'))
      .catch((err) => {
        setHealthStatus('error');
        console.error('API Health check failed:', err);
      });
  }, []);

  // Fetch list of run reports based on current filter state
  const fetchReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.listRuns(filters);
      const reportList = response?.reports || [];
      setReports(reportList);

      // If selected report is no longer in the fetched list, clear selection
      if (selectedReport && !reportList.some((r) => r.run_id === selectedReport.run_id)) {
        setSelectedReport(null);
      }
    } catch (err) {
      setError(err.message || 'Failed to load run reports.');
    } finally {
      setLoading(false);
    }
  }, [filters, selectedReport]);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  // Handle selecting a run to inspect details
  const handleSelectRun = async (runId) => {
    if (selectedReport?.run_id === runId) {
      setSelectedReport(null);
      return;
    }

    setDetailLoading(true);
    try {
      const detail = await api.getRunDetails(runId);
      setSelectedReport(detail);
    } catch (err) {
      setError(`Failed to fetch details for run '${runId}': ${err.message}`);
    } finally {
      setDetailLoading(false);
    }
  };

  // Handle deleting a run report
  const handleDeleteRun = async (runId) => {
    if (!window.confirm(`Are you sure you want to delete run '${runId}'?`)) {
      return;
    }

    try {
      await api.deleteRun(runId);
      if (selectedReport?.run_id === runId) {
        setSelectedReport(null);
      }
      fetchReports();
    } catch (err) {
      setError(`Failed to delete run '${runId}': ${err.message}`);
    }
  };

  // Handle filter changes
  const handleFilterChange = (newFilters) => {
    setFilters(newFilters);
  };

  // Handle resetting filters
  const handleResetFilters = () => {
    setFilters({ agent_id: '', test_case_id: '', limit: '' });
  };

  // Navigate between views, optionally carrying a filter (e.g. "View Runs"
  // from the Agents view pre-filters the Runs view to that agent).
  const handleNavigate = (view, params = {}) => {
    if (params.agentId) {
      setFilters((prev) => ({ ...prev, agent_id: params.agentId }));
    }
    setCurrentView(view);
  };

  // Extract recent 5 runs for Dashboard high-level preview
  const recentRuns = reports.slice(0, 5);

  return (
    <div className="app-shell">
      <Sidebar currentView={currentView} onNavigate={handleNavigate} />

      <div className="app-shell__content">
        {/* Top Header Navigation */}
        <header className="app-header">
          <div className="app-header__brand">
            <div className="app-header__mark" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M12 2L2 7v6c0 5.25 3.75 9.75 10 11 6.25-1.25 10-5.75 10-11V7l-10-5z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
                <path
                  d="M9 12l2 2 4-4"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
            <div>
              <h1 className="app-header__title">AI Agent Reliability &amp; Security Platform</h1>
              <p className="app-header__subtitle">Evaluation &middot; Security &middot; Observability</p>
            </div>
          </div>

          <div className={`health-pill health-pill--${healthStatus}`}>
            <span className="health-pill__dot" />
            <span>
              API {healthStatus === 'ok' ? 'Operational' : healthStatus === 'error' ? 'Unavailable' : 'Checking…'}
            </span>
          </div>
        </header>

        {/* Main Container */}
        <main className="app-main">
          {error && <ErrorAlert message={error} onRetry={fetchReports} />}

          {/* VIEW 1: DASHBOARD */}
          {currentView === 'dashboard' && (
            <>
              {/* Platform Health Status Card */}
              <section className="panel" style={{ marginBottom: '20px', padding: '16px 20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        width: '10px',
                        height: '10px',
                        borderRadius: '50%',
                        backgroundColor:
                          healthStatus === 'ok' ? '#10B981' : healthStatus === 'error' ? '#EF4444' : '#F59E0B',
                        boxShadow: `0 0 8px ${
                          healthStatus === 'ok'
                            ? 'rgba(16, 185, 129, 0.5)'
                            : healthStatus === 'error'
                            ? 'rgba(239, 68, 68, 0.5)'
                            : 'rgba(245, 158, 11, 0.5)'
                        }`,
                      }}
                    />
                    <div>
                      <span style={{ fontSize: '0.85rem', color: '#94A3B8', fontWeight: 500 }}>
                        Platform Health Status
                      </span>
                      <h3 style={{ margin: '2px 0 0 0', fontSize: '1rem', color: '#F8FAFC' }}>
                        API Engine:{' '}
                        {healthStatus === 'ok'
                          ? 'Operational'
                          : healthStatus === 'error'
                          ? 'Unavailable'
                          : 'Checking System Status…'}
                      </h3>
                    </div>
                  </div>
                  <span style={{ fontSize: '0.8rem', color: '#64748B' }}>FastAPI Backend Health</span>
                </div>
              </section>

              {/* High Level KPI Overview Cards */}
              <DashboardOverview reports={reports} />

              {/* Modal/Detail view when inspecting a recent run */}
              {detailLoading && <LoadingSpinner message="Fetching detailed report..." size={28} />}
              {!detailLoading && selectedReport && (
                <RunDetailView report={selectedReport} onClose={() => setSelectedReport(null)} />
              )}

              {/* Lower Section: Recent Activity Cards */}
              <section className="panel">
                <div className="panel__header">
                  <div>
                    <h2 className="panel__title">Recent Activity</h2>
                    <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#94A3B8' }}>
                      Latest 5 execution summaries
                    </p>
                  </div>
                  <button
                    onClick={() => setCurrentView('runs')}
                    className="btn btn--secondary"
                    style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <span>View all runs</span>
                    <span aria-hidden="true">&rarr;</span>
                  </button>
                </div>

                {loading ? (
                  <LoadingSpinner message="Loading recent execution reports..." />
                ) : recentRuns.length === 0 ? (
                  <div style={{ padding: '32px', textAlign: 'center', color: '#64748B' }}>
                    No recent execution runs found.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gap: '12px', marginTop: '12px' }}>
                    {recentRuns.map((run) => {
                      // 1. Status Mapping: overall_status ?? status
                      const rawStatus = run.overall_status ?? run.status;
                      const statusUpper = String(rawStatus || '').toUpperCase().trim();
                      const passed =
                        statusUpper === 'PASS' ||
                        statusUpper === 'PASSED' ||
                        statusUpper === 'SUCCESS';

                      // 2. Score Mapping: overall_score ?? score ?? metrics?.overall_score ?? metrics?.score
                      const rawScore =
                        run.overall_score ??
                        run.score ??
                        run.metrics?.overall_score ??
                        run.metrics?.score;

                      let scoreDisplay = 'N/A';
                      if (rawScore !== undefined && rawScore !== null && rawScore !== '') {
                        const numScore = Number(rawScore);
                        if (!isNaN(numScore)) {
                          const normalized =
                            numScore <= 1 ? Math.round(numScore * 100) : Math.round(numScore);
                          scoreDisplay = `${normalized}%`;
                        }
                      }

                      // 3. Duration Mapping: execution?.duration ?? duration ?? metrics?.duration ?? execution_time
                     const rawDuration =
  run.duration_ms ??
  run.execution?.duration ??
  run.duration ??
  run.metrics?.duration ??
  run.execution_time ??
  run.latency;

                      let durationDisplay = 'N/A';
                      if (rawDuration !== undefined && rawDuration !== null && rawDuration !== '') {
                        const numDuration = Number(rawDuration);
                        if (!isNaN(numDuration)) {
                          durationDisplay =
                            numDuration < 10
                              ? `${numDuration.toFixed(2)}s`
                              : `${Math.round(numDuration)}s`;
                        } else {
                          durationDisplay = String(rawDuration);
                        }
                      }

                      const displayStatus = passed ? 'PASS' : statusUpper || 'FAILED';

                      return (
                        <div
                          key={run.run_id || run.id}
                          onClick={() => handleSelectRun(run.run_id || run.id)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '14px 18px',
                            backgroundColor: 'rgba(30, 41, 59, 0.4)',
                            border: '1px solid rgba(255, 255, 255, 0.06)',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(30, 41, 59, 0.8)';
                            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.15)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'rgba(30, 41, 59, 0.4)';
                            e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.06)';
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                            <span
                              style={{
                                padding: '4px 8px',
                                borderRadius: '4px',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                backgroundColor: passed
                                  ? 'rgba(16, 185, 129, 0.15)'
                                  : 'rgba(239, 68, 68, 0.15)',
                                color: passed ? '#10B981' : '#EF4444',
                              }}
                            >
                              {displayStatus}
                            </span>
                            <div>
                              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#F8FAFC' }}>
                                {run.run_id || run.id}
                              </div>
                              <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>
                                Agent: <span style={{ color: '#CBD5E1' }}>{run.agent_id || 'N/A'}</span>
                              </div>
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                            <div style={{ textAlign: 'right' }}>
                              <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Overall Score</div>
                              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#F8FAFC' }}>
                                {scoreDisplay}
                              </div>
                            </div>
                            <div style={{ textAlign: 'right', minWidth: '70px' }}>
                              <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Duration</div>
                              <div style={{ fontSize: '0.85rem', color: '#94A3B8' }}>{durationDisplay}</div>
                            </div>
                            <svg
                              width="16"
                              height="16"
                              viewBox="0 0 24 24"
                              fill="none"
                              xmlns="http://www.w3.org/2000/svg"
                              style={{ color: '#64748B' }}
                            >
                              <path
                                d="M9 18l6-6-6-6"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                            </svg>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            </>
          )}

          {/* VIEW 2: RUNS */}
          {currentView === 'runs' && (
            <>
              <section className="panel" style={{ marginBottom: '20px' }}>
                <div className="panel__header">
                  <div>
                    <h2 className="panel__title" style={{ fontSize: '1.25rem' }}>
                      Runs
                    </h2>
                    <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#94A3B8' }}>
                      Inspect and analyze AI agent executions
                    </p>
                  </div>
                  <button onClick={fetchReports} disabled={loading} className="btn btn--secondary">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path
                        d="M21 12a9 9 0 1 1-3-6.7M21 4v5h-5"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    Refresh
                  </button>
                </div>
              </section>

              <FilterBar filters={filters} onFilterChange={handleFilterChange} onReset={handleResetFilters} />

              {detailLoading && <LoadingSpinner message="Fetching detailed report..." size={28} />}
              {!detailLoading && selectedReport && (
                <RunDetailView report={selectedReport} onClose={() => setSelectedReport(null)} />
              )}

              <section className="panel">
                <div className="panel__header">
                  <h2 className="panel__title">
                    Execution Logs <span className="panel__count">{reports.length}</span>
                  </h2>
                </div>

                {loading ? (
                  <LoadingSpinner message="Loading execution reports..." />
                ) : (
                  <RunHistoryTable
                    reports={reports}
                    selectedRunId={selectedReport?.run_id}
                    onSelectRun={handleSelectRun}
                    onDeleteRun={handleDeleteRun}
                  />
                )}
              </section>
            </>
          )}

{/* VIEW 3: AGENTS */}
{currentView === 'agents' && (
  <>
    {detailLoading && <LoadingSpinner message="Fetching detailed report..." size={28} />}
    {!detailLoading && selectedReport && (
      <RunDetailView report={selectedReport} onClose={() => setSelectedReport(null)} />
    )}

    <AgentsView
      reports={reports}
      loading={loading}
      onRefresh={fetchReports}
      onSelectRun={handleSelectRun}
      onNavigate={handleNavigate}
      selectedRunId={selectedReport?.run_id}
    />
  </>
)}
{/* VIEW 4: TEST CASES */}
{currentView === 'test-cases' && (
  <TestCasesView />
)}

{/* VIEW 5: REPORTS */}
{currentView === 'reports' && (
  <section className="panel">
    <div className="panel__header">
      <div>
        <h2 className="panel__title">Reports</h2>
        <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#94A3B8' }}>
          Execution performance and evaluation reports
        </p>
      </div>

      <span className="panel__count">{reports.length}</span>
    </div>

    {reports.length === 0 ? (
      <div className="state-block">
        <span>No reports available.</span>
      </div>
    ) : (
      <div style={{ display: 'grid', gap: '12px' }}>
        {reports.map((report) => {
          const score = report.overall_score;
          const durationMs = getDurationMs(report);
          const totalTokens = getTotalTokens(report);
          const totalCost = getTotalCostUsd(report);

          return (
            <div
              key={report.run_id}
              style={{
                padding: '16px',
                background: 'rgba(30, 41, 59, 0.4)',
                border: '1px solid rgba(255, 255, 255, 0.06)',
                borderRadius: '8px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '10px',
                }}
              >
                <div>
                  <strong style={{ color: '#F8FAFC' }}>
                    {report.run_id}
                  </strong>

                  <div
                    style={{
                      fontSize: '0.75rem',
                      color: '#64748B',
                      marginTop: '3px',
                    }}
                  >
                    Agent: {report.agent_id}
                  </div>
                </div>

                <strong
                  style={{
                    color: isPassStatus(report.overall_status) ? '#10B981' : '#EF4444',
                  }}
                >
                  {report.overall_status?.toUpperCase()}
                </strong>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '12px',
                  fontSize: '0.8rem',
                  color: '#CBD5E1',
                }}
              >
                <div>
                  <strong>Score</strong>
                  <div>{score ?? 'N/A'}%</div>
                </div>

                <div>
                  <strong>Duration</strong>
                  <div>{durationMs != null ? `${durationMs}ms` : 'N/A'}</div>
                </div>

                <div>
                  <strong>Tokens</strong>
                  <div>{totalTokens ?? 'N/A'}</div>
                </div>

                <div>
                  <strong>Cost</strong>
                  <div>
                    {totalCost != null
                      ? `$${Number(totalCost).toFixed(4)}`
                      : 'N/A'}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    )}
  </section>
)}
{/* VIEW 6: ALERTS */}
{currentView === 'alerts' && (
  <AlertsView
    alerts={reports.flatMap((report) =>
      (report.security?.findings || []).map((finding) => {
        const severity = String(finding.severity || 'LOW').toUpperCase();
        return {
          id: `${report.run_id}:${finding.finding_id || finding.category}`,
          name: `${finding.category} — ${severity}`,
          message: `${finding.message} (Agent: ${report.agent_id || 'N/A'}, Run: ${report.run_id || 'N/A'})`,
          // Display-only scale derived from the backend's real severity.
          riskScore: SEVERITY_RISK[severity] ?? 50,
          severity,
          status: report.overall_status || 'FAIL',
          agentId: report.agent_id,
        };
      })
    )}
  />
)}

{/* VIEW 5: SETTINGS */}
{currentView === 'settings' && (
  <SettingsView />
)}
        </main>
      </div>
    </div>
  );
}

export default App;