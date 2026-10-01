import React from 'react';

/**
 * LoadingSpinner Component
 * Reusable centered loading spinner for async dashboard API calls.
 *
 * Props:
 * - message: string (optional loading text below spinner)
 * - size: number (diameter in pixels, default 36)
 */
export const LoadingSpinner = ({ message = 'Loading...', size = 36 }) => {
  return (
    <div className="state-block">
      <div
        className="spinner"
        style={{ width: `${size}px`, height: `${size}px` }}
      />
      {message && <span>{message}</span>}
    </div>
  );
};

export default LoadingSpinner;
