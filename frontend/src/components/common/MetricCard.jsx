import React from 'react';

const STATUS_STYLES = {
  success: { bg: 'rgba(34, 197, 94, 0.14)', color: '#4ade80' },
  warning: { bg: 'rgba(245, 158, 11, 0.14)', color: '#fbbf24' },
  error: { bg: 'rgba(244, 63, 94, 0.14)', color: '#fb7185' },
  neutral: { bg: 'rgba(100, 116, 139, 0.16)', color: '#94a3b8' },
};

const ICONS = {
  success: (
    <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  ),
  warning: (
    <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  ),
  error: (
    <path d="M12 8v4m0 4h.01M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  ),
  neutral: (
    <path d="M4 19h16M4 15h10M4 11h16M4 7h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
  ),
};

/**
 * MetricCard Component
 * Displays a single aggregate/detail metric with a label, large value,
 * optional subtitle, and a status-colored icon for quick visual scanning.
 *
 * Props:
 * - title: string
 * - value: string | number
 * - subtitle: string (optional)
 * - status: 'success' | 'warning' | 'error' | 'neutral'
 */
export const MetricCard = ({ title, value, subtitle, status = 'neutral' }) => {
  const style = STATUS_STYLES[status] || STATUS_STYLES.neutral;

  return (
    <div className="metric-card">
      <div className="metric-card__top">
        <span className="metric-card__label">{title}</span>
        <div className="metric-card__icon" style={{ background: style.bg, color: style.color }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            {ICONS[status] || ICONS.neutral}
          </svg>
        </div>
      </div>
      <div className="metric-card__value">{value}</div>
      {subtitle && <div className="metric-card__hint">{subtitle}</div>}
    </div>
  );
};

export default MetricCard;
