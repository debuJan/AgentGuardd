import React from 'react';
import MetricCard from './common/MetricCard';

/**
 * DashboardOverview Component
 * Computes and displays aggregate metrics (total runs, pass/fail counts, average scores)
 * across retrieved UnifiedRunReport objects.
 *
 * Props:
 * - reports: Array of UnifiedRunReport objects
 */
export const DashboardOverview = ({ reports = [] }) => {
  if (!reports || reports.length === 0) {
    return (
      <div className="metrics-grid">
        <MetricCard title="Total Runs" value={0} status="neutral" />
        <MetricCard title="Pass Rate" value="0%" status="neutral" />
        <MetricCard title="Avg Score" value="N/A" status="neutral" />
        <MetricCard title="Avg Reliability" value="N/A" status="neutral" />
        <MetricCard title="Avg Security" value="N/A" status="neutral" />
      </div>
    );
  }

  const totalRuns = reports.length;

  // Helper: Consistent Pass Status check
  const isPassStatus = (r) => {
    const status = String(r.overall_status ?? r.status ?? '').toUpperCase().trim();
    return status === 'PASS' || status === 'PASSED' || status === 'SUCCESS';
  };

  // Calculate Pass/Fail counts
  const passedRuns = reports.filter(isPassStatus).length;
  const failedRuns = totalRuns - passedRuns;
  const passRate = totalRuns > 0 ? ((passedRuns / totalRuns) * 100).toFixed(1) : 0;

  // Helper: Calculate Average Scores with 0-1 to 0-100 normalization support
  const calculateAverage = (extractor) => {
    const validScores = reports
      .map(extractor)
      .filter((score) => typeof score === 'number' && !isNaN(score));

    if (validScores.length === 0) return null;

    const normalizedScores = validScores.map((val) => (val <= 1 ? val * 100 : val));
    const sum = normalizedScores.reduce((acc, val) => acc + val, 0);
    return (sum / normalizedScores.length).toFixed(1);
  };

  const avgOverallScore = calculateAverage((r) => r.overall_score ?? r.score);
  const avgReliabilityScore = calculateAverage((r) => r.reliability?.reliability_score);
  const avgSecurityScore = calculateAverage((r) => r.security?.security_score);

  // Determine status indicators for MetricCards
  const passRateStatus =
    passRate >= 80 ? 'success' : passRate >= 50 ? 'warning' : 'error';
  const overallStatus =
    avgOverallScore >= 80 ? 'success' : avgOverallScore >= 50 ? 'warning' : 'error';

  return (
    <div className="metrics-grid">
      <MetricCard
        title="Total Runs"
        value={totalRuns}
        subtitle={`${passedRuns} Passed / ${failedRuns} Failed`}
        status="neutral"
      />
      <MetricCard
        title="Pass Rate"
        value={`${passRate}%`}
        subtitle={`${passedRuns} of ${totalRuns} successful`}
        status={passRateStatus}
      />
      <MetricCard
        title="Avg Overall Score"
        value={avgOverallScore !== null ? `${avgOverallScore}%` : 'N/A'}
        status={overallStatus}
      />
      <MetricCard
        title="Avg Reliability"
        value={avgReliabilityScore !== null ? `${avgReliabilityScore}%` : 'N/A'}
        status={
          avgReliabilityScore === null
            ? 'neutral'
            : avgReliabilityScore >= 80
            ? 'success'
            : avgReliabilityScore >= 50
            ? 'warning'
            : 'error'
        }
      />
      <MetricCard
        title="Avg Security"
        value={avgSecurityScore !== null ? `${avgSecurityScore}%` : 'N/A'}
        status={
          avgSecurityScore === null
            ? 'neutral'
            : avgSecurityScore >= 80
            ? 'success'
            : avgSecurityScore >= 50
            ? 'warning'
            : 'error'
        }
      />
    </div>
  );
};

export default DashboardOverview;