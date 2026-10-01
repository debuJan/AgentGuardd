import React from 'react';
import StatusBadge from './common/StatusBadge';
import MetricCard from './common/MetricCard';

/**
 * RunDetailView Component
 * Renders a comprehensive breakdown of a single UnifiedRunReport.
 *
 * Displays:
 * - Overall score/status
 * - Reliability
 * - Security
 * - Observability metrics
 * - Token usage and cost
 * - Reliability failures
 * - Security findings
 * - Complete event-by-event execution trace
 *
 * Props:
 * - report: UnifiedRunReport object
 * - onClose: function() (callback to close or deselect the detail view)
 */
export const RunDetailView = ({ report, onClose }) => {
  if (!report) return null;

  const {
    run_id,
    agent_id,
    test_case_id,
    overall_status,
    overall_score,
    reliability = {},
    security = {},
    metrics = {},
    trace = null,
  } = report;

  const formatDuration = (ms) => {
    if (ms === undefined || ms === null) return 'N/A';
    if (ms < 1000) return `${Number(ms).toFixed(2)}ms`;
    return `${(Number(ms) / 1000).toFixed(2)}s`;
  };

  const formatCost = (cost) => {
    if (cost === undefined || cost === null) return 'N/A';
    return `$${Number(cost).toFixed(5)}`;
  };

  const toolErrors = metrics.tool_errors || metrics.errors || [];
  const repeatedCalls =
    metrics.repeated_tool_calls || metrics.repeated_calls || [];

  const failures = reliability.failures || reliability.errors || [];
  const findings = security.findings || security.vulnerabilities || [];

  // Real execution trace from the backend
  const traceEvents = trace?.events || [];

  const reliabilityScore = reliability.reliability_score;
  const securityScore = security.security_score;

  const getEventLabel = (event) => {
    switch (event?.type) {
      case 'llm_call':
        return 'LLM Call';
      case 'tool_call':
        return 'Tool Call';
      case 'tool_result':
        return 'Tool Result';
      case 'tool_error':
        return 'Tool Error';
      case 'final_response':
        return 'Final Response';
      case 'run_error':
        return 'Run Error';
      default:
        return event?.type || 'Unknown Event';
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
      return timestamp;
    }

    return date.toLocaleTimeString();
  };

  const renderEventContent = (event) => {
    switch (event?.type) {
      case 'llm_call':
        return (
          <>
            {event.input && (
              <div style={{ marginBottom: 8 }}>
                <strong>Input</strong>
                <pre className="trace-event__json">
                  {event.input}
                </pre>
              </div>
            )}

            {event.output && (
              <div style={{ marginBottom: 8 }}>
                <strong>Output</strong>
                <pre className="trace-event__json">
                  {event.output}
                </pre>
              </div>
            )}

            {event.tool_calls_requested?.length > 0 && (
              <div>
                <strong>Tools Requested</strong>
                <pre className="trace-event__json">
                  {JSON.stringify(event.tool_calls_requested, null, 2)}
                </pre>
              </div>
            )}
          </>
        );

      case 'tool_call':
        return (
          <>
            <div style={{ marginBottom: 8 }}>
              <strong>Tool</strong>
              <div className="trace-event__value">
                {event.tool_name || 'Unknown tool'}
              </div>
            </div>

            <div>
              <strong>Arguments</strong>
              <pre className="trace-event__json">
                {JSON.stringify(event.arguments || {}, null, 2)}
              </pre>
            </div>
          </>
        );

      case 'tool_result':
        return (
          <>
            <div style={{ marginBottom: 8 }}>
              <strong>Tool</strong>
              <div className="trace-event__value">
                {event.tool_name || 'Unknown tool'}
              </div>
            </div>

            <div>
              <strong>Result</strong>
              <pre className="trace-event__json">
                {typeof event.result === 'string'
                  ? event.result
                  : JSON.stringify(event.result, null, 2)}
              </pre>
            </div>
          </>
        );

      case 'tool_error':
        return (
          <>
            <div style={{ marginBottom: 8 }}>
              <strong>Tool</strong>
              <div className="trace-event__value">
                {event.tool_name || 'Unknown tool'}
              </div>
            </div>

            <div>
              <strong>Error</strong>
              <pre className="trace-event__json">
                {event.error || 'Unknown tool error'}
              </pre>
            </div>
          </>
        );

      case 'final_response':
        return (
          <div>
            <strong>Response</strong>
            <pre className="trace-event__json">
              {event.content || ''}
            </pre>
          </div>
        );

      case 'run_error':
        return (
          <div>
            <strong>Error</strong>
            <pre className="trace-event__json">
              {event.error || 'Unknown run error'}
            </pre>
          </div>
        );

      default:
        return (
          <pre className="trace-event__json">
            {JSON.stringify(event, null, 2)}
          </pre>
        );
    }
  };

  return (
    <div className="detail-panel">
      {/* Header Section */}
      <div className="detail-panel__header">
        <div>
          <div className="detail-panel__title">
            Run Detail: {run_id}
            <StatusBadge status={overall_status} />
          </div>

          <div
            style={{
              fontSize: '0.8rem',
              color: '#94a3b8',
              marginTop: 4,
            }}
          >
            Agent:{' '}
            <strong style={{ color: '#e2e8f0' }}>
              {agent_id}
            </strong>{' '}
            &nbsp;·&nbsp; Test Case:{' '}
            <strong style={{ color: '#e2e8f0' }}>
              {test_case_id}
            </strong>
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="btn"
            style={{
              background: 'rgba(255,255,255,0.08)',
              color: '#e2e8f0',
              border: '1px solid rgba(255,255,255,0.14)',
            }}
          >
            Close
          </button>
        )}
      </div>

      <div style={{ padding: 20 }}>
        {/* Top Metrics Cards */}
        <div className="metrics-grid" style={{ marginBottom: 20 }}>
          <MetricCard
            title="Overall Score"
            value={
              overall_score !== undefined
                ? `${overall_score}%`
                : 'N/A'
            }
            status={
              overall_score >= 80
                ? 'success'
                : overall_score >= 50
                  ? 'warning'
                  : 'error'
            }
          />

          <MetricCard
            title="Reliability Score"
            value={
              reliabilityScore !== undefined
                ? `${reliabilityScore}%`
                : 'N/A'
            }
            subtitle={`Status: ${
              reliability.passed !== undefined
                ? reliability.passed
                  ? 'PASS'
                  : 'FAIL'
                : 'N/A'
            }`}
            status={
              reliabilityScore >= 80
                ? 'success'
                : reliabilityScore >= 50
                  ? 'warning'
                  : 'error'
            }
          />

          <MetricCard
            title="Security Score"
            value={
              securityScore !== undefined
                ? `${securityScore}%`
                : 'N/A'
            }
            subtitle={`Passed: ${
              security.passed !== undefined
                ? String(security.passed)
                : 'N/A'
            }`}
            status={
              securityScore >= 80
                ? 'success'
                : securityScore >= 50
                  ? 'warning'
                  : 'error'
            }
          />

          <MetricCard
            title="Total Cost"
            value={formatCost(metrics.cost?.total_cost)}
            subtitle={`Duration: ${formatDuration(report.duration_ms)}`}
            status="neutral"
          />
        </div>

        {/* Observability & Token Metrics */}
        <div
          style={{
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            padding: 16,
            marginBottom: 20,
          }}
        >
          <h3
            style={{
              margin: '0 0 14px',
              fontSize: '0.85rem',
              fontWeight: 650,
              color: '#334155',
            }}
          >
            Observability &amp; Tokens
          </h3>

          <div
            className="detail-panel__body"
            style={{ padding: 0 }}
          >
            <div className="detail-field">
              <span className="detail-field__label">
                Prompt Tokens
              </span>

              <span className="detail-field__value">
                {metrics.tokens?.input_tokens != null
                  ? metrics.tokens.input_tokens.toLocaleString()
                  : 'N/A'}
              </span>
            </div>

            <div className="detail-field">
              <span className="detail-field__label">
                Completion Tokens
              </span>

              <span className="detail-field__value">
                {metrics.tokens?.output_tokens != null
                  ? metrics.tokens.output_tokens.toLocaleString()
                  : 'N/A'}
              </span>
            </div>

            <div className="detail-field">
              <span className="detail-field__label">
                Total Tokens
              </span>

              <span className="detail-field__value">
                {metrics.tokens?.total_tokens != null
                  ? metrics.tokens.total_tokens.toLocaleString()
                  : 'N/A'}
              </span>
            </div>

            <div className="detail-field">
              <span className="detail-field__label">
                Latency
              </span>

              <span className="detail-field__value">
                {formatDuration(report.duration_ms)}
              </span>
            </div>
          </div>
        </div>

        {/* Failures & Security Findings */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns:
              'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 16,
            marginBottom: 20,
          }}
        >
          {/* Reliability Failures */}
          <div
            style={{
              border: '1px solid #e2e8f0',
              borderRadius: 10,
              padding: 16,
            }}
          >
            <h4
              style={{
                margin: '0 0 10px',
                fontSize: '0.82rem',
                fontWeight: 650,
                color: '#0f172a',
              }}
            >
              Reliability Failures{' '}
              <span className="badge badge--neutral">
                {failures.length}
              </span>
            </h4>

            {failures.length === 0 ? (
              <span className="badge badge--success">
                No failures
              </span>
            ) : (
              <ul
                style={{
                  margin: 0,
                  paddingLeft: 18,
                  fontSize: '0.8rem',
                  color: '#991b1b',
                  lineHeight: 1.7,
                }}
              >
                {failures.map((fail, idx) => (
                  <li key={idx}>
                    {typeof fail === 'string'
                      ? fail
                      : JSON.stringify(fail)}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Security Findings */}
          <div
            style={{
              border: '1px solid #e2e8f0',
              borderRadius: 10,
              padding: 16,
            }}
          >
            <h4
              style={{
                margin: '0 0 10px',
                fontSize: '0.82rem',
                fontWeight: 650,
                color: '#0f172a',
              }}
            >
              Security Findings{' '}
              <span className="badge badge--neutral">
                {findings.length}
              </span>
            </h4>

            {findings.length === 0 ? (
              <span className="badge badge--success">
                No findings
              </span>
            ) : (
              <ul
                style={{
                  margin: 0,
                  paddingLeft: 18,
                  fontSize: '0.8rem',
                  color: '#991b1b',
                  lineHeight: 1.7,
                }}
              >
                {findings.map((finding, idx) => (
                  <li key={idx}>
                    {typeof finding === 'string'
                      ? finding
                      : JSON.stringify(finding)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Complete Execution Trace */}
        <div
          style={{
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            padding: 16,
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 12,
            }}
          >
            <h3
              style={{
                margin: 0,
                fontSize: '0.85rem',
                fontWeight: 650,
                color: '#334155',
              }}
            >
              Execution Trace
            </h3>

            <span className="badge badge--neutral">
              {traceEvents.length} event
              {traceEvents.length === 1 ? '' : 's'}
            </span>
          </div>

          {!trace ? (
            <div
              style={{
                fontSize: '0.8rem',
                color: '#64748b',
              }}
            >
              No execution trace is available for this run.
            </div>
          ) : traceEvents.length === 0 ? (
            <div
              style={{
                fontSize: '0.8rem',
                color: '#64748b',
              }}
            >
              The execution trace contains no events.
            </div>
          ) : (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              {traceEvents.map((event, index) => (
                <div
                  key={`${event.timestamp || 'event'}-${index}`}
                  style={{
                    border: '1px solid #e2e8f0',
                    borderRadius: 8,
                    overflow: 'hidden',
                    background: '#ffffff',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '10px 12px',
                      background: '#f8fafc',
                      borderBottom:
                        '1px solid #e2e8f0',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                      }}
                    >
                      <span
                        style={{
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          color: '#64748b',
                        }}
                      >
                        #{index + 1}
                      </span>

                      <strong
                        style={{
                          fontSize: '0.8rem',
                          color: '#0f172a',
                        }}
                      >
                        {getEventLabel(event)}
                      </strong>
                    </div>

                    <span
                      style={{
                        fontSize: '0.7rem',
                        color: '#64748b',
                      }}
                    >
                      {formatTimestamp(event.timestamp)}
                    </span>
                  </div>

                  <div
                    style={{
                      padding: 12,
                      fontSize: '0.78rem',
                      color: '#334155',
                    }}
                  >
                    {renderEventContent(event)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RunDetailView;