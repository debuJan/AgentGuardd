import React from 'react';

/**
 * ErrorAlert Component
 * Reusable error message banner for API and UI runtime failures.
 *
 * Props:
 * - message: string | Error
 * - onRetry: function (optional)
 * - title: string (optional banner header)
 */
export const ErrorAlert = ({ message, onRetry, title = 'Error Loading Data' }) => {
  const errorMessage =
    message instanceof Error ? message.message : message || 'An unexpected error occurred.';

  return (
    <div className="alert">
      <svg className="alert__icon" width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 8v4m0 4h.01M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"
          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 650, marginBottom: 2 }}>{title}</div>
        <div style={{ color: '#fda4af', lineHeight: 1.4 }}>{errorMessage}</div>
      </div>
      {onRetry && (
        <div className="alert__actions">
          <button onClick={onRetry} className="btn btn--danger">
            Retry
          </button>
        </div>
      )}
    </div>
  );
};

export default ErrorAlert;
