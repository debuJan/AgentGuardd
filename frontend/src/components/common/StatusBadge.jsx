import React from 'react';

/**
 * StatusBadge Component
 * Renders a colored pill badge for a run's overall status.
 *
 * Props:
 * - status: string (e.g. "PASS", "FAIL", "PASSED", "FAILED", etc.)
 */
export const StatusBadge = ({ status }) => {
  const normalized = (status || '').toUpperCase();
  const isPass = normalized === 'PASS' || normalized === 'PASSED' || normalized === 'SUCCESS';
  const isFail = normalized === 'FAIL' || normalized === 'FAILED' || normalized === 'ERROR';

  const variant = isPass ? 'success' : isFail ? 'danger' : 'neutral';

  return (
    <span className={`badge badge--${variant}`}>
      <span
        style={{
          width: 5,
          height: 5,
          borderRadius: '50%',
          background: 'currentColor',
          display: 'inline-block',
        }}
      />
      {status || 'UNKNOWN'}
    </span>
  );
};

export default StatusBadge;
