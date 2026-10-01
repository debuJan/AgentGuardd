import React from 'react';
import StatusBadge from './common/StatusBadge';
import { getDurationMs, getTotalCostUsd, getTotalTokens } from '../utils/reportFields';

/**
 * RunHistoryTable Component
 * Displays a list of execution reports with key metrics (run ID, agent ID,
 * test case ID, overall score, status, duration, tokens, cost).
 * Provides interactive callbacks for selecting and deleting runs.
 *
 * Props:
 * - reports: Array of UnifiedRunReport objects
 * - selectedRunId: string (currently selected run ID for row highlighting)
 * - onSelectRun: function(runId)
 * - onDeleteRun: function(runId)
 */
export const RunHistoryTable = ({
  reports = [],
  selectedRunId,
  onSelectRun,
  onDeleteRun,
}) => {
  if (!reports || reports.length === 0) {
    return (
      <div className="state-block">
        <span>No run reports found.</span>
      </div>
    );
  }

  const formatDuration = (ms) => {
    if (ms === undefined || ms === null) return 'N/A';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatCost = (cost) => {
    if (cost === undefined || cost === null) return 'N/A';
    return `$${Number(cost).toFixed(4)}`;
  };

  const formatTokens = (tokens) => {
    if (tokens === undefined || tokens === null) return 'N/A';
    return Number(tokens).toLocaleString();
  };

  const scoreColor = (score) => {
    if (score === undefined || score === null) return '#94a3b8';
    if (score >= 80) return '#059669';
    if (score >= 50) return '#d97706';
    return '#dc2626';
  };

  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>Run ID</th>
            <th>Agent ID</th>
            <th>Test Case ID</th>
            <th>Status</th>
            <th>Score</th>
            <th>Duration</th>
            <th>Tokens</th>
            <th>Cost</th>
            <th style={{ textAlign: 'right' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {reports.map((report) => {
            const isSelected = report.run_id === selectedRunId;
            const totalTokens = getTotalTokens(report);
            const totalCost = getTotalCostUsd(report);
            const durationMs = getDurationMs(report);
            const score = report.overall_score;
            const color = scoreColor(score);

            return (
              <tr
                key={report.run_id}
                onClick={() => onSelectRun && onSelectRun(report.run_id)}
                className={isSelected ? 'is-selected' : ''}
              >
                <td style={{ fontWeight: 650, color: '#0f172a' }}>{report.run_id}</td>
                <td>{report.agent_id}</td>
                <td>{report.test_case_id}</td>
                <td>
                  <StatusBadge status={report.overall_status} />
                </td>
                <td>
                  {score !== undefined && score !== null ? (
                    <div className="score-bar">
                      <div className="score-bar__track">
                        <div
                          className="score-bar__fill"
                          style={{ width: `${Math.min(100, Math.max(0, score))}%`, background: color }}
                        />
                      </div>
                      <span className="score-bar__label" style={{ color }}>
                        {score}%
                      </span>
                    </div>
                  ) : (
                    <span style={{ color: '#94a3b8' }}>N/A</span>
                  )}
                </td>
                <td>{formatDuration(durationMs)}</td>
                <td>{formatTokens(totalTokens)}</td>
                <td>{formatCost(totalCost)}</td>
                <td style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => onDeleteRun && onDeleteRun(report.run_id)}
                    className="btn btn--danger"
                    style={{ padding: '5px 10px', fontSize: '0.75rem' }}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default RunHistoryTable;
