/**
 * reportFields.js
 *
 * Display-field extractors for UnifiedRunReport objects as returned by
 * GET /runs and GET /runs/{run_id}.
 *
 * Canonical paths on the backend model:
 *   - duration: report.metrics.duration_ms        (observability RunMetrics)
 *   - tokens:   report.metrics.tokens.total_tokens (TokenMetrics)
 *   - cost:     report.metrics.cost.total_cost     (CostBreakdown, ESTIMATED)
 *
 * The top-level report.duration_ms / report.total_tokens /
 * report.estimated_cost_usd are kept as fallbacks for rows saved by older
 * backend versions. Never invent a value: return null when absent and let
 * callers render "N/A".
 */

export const getDurationMs = (report) =>
  report?.metrics?.duration_ms ?? report?.duration_ms ?? null;

export const getTotalTokens = (report) =>
  report?.metrics?.tokens?.total_tokens ?? report?.total_tokens ?? null;

export const getTotalCostUsd = (report) =>
  report?.metrics?.cost?.total_cost ?? report?.estimated_cost_usd ?? null;

/** Case-insensitive pass check for overall_status ("success" from the API). */
export const isPassStatus = (status) => {
  const s = String(status ?? '').toUpperCase().trim();
  return s === 'PASS' || s === 'PASSED' || s === 'SUCCESS';
};
