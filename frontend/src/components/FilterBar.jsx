import React, { useState, useEffect } from 'react';

/**
 * FilterBar Component
 * Allows filtering run reports by agent_id, test_case_id, and limit.
 *
 * Props:
 * - filters: { agent_id: string, test_case_id: string, limit: string | number }
 * - onFilterChange: function(updatedFilters)
 * - onReset: function()
 */
export const FilterBar = ({ filters = {}, onFilterChange, onReset }) => {
  const [agentId, setAgentId] = useState(filters.agent_id || '');
  const [testCaseId, setTestCaseId] = useState(filters.test_case_id || '');
  const [limit, setLimit] = useState(filters.limit || '');

  // Stay in sync when the parent changes filters externally
  // (e.g. "View Runs" from the Agents view pre-fills the agent filter,
  // or a reset is triggered elsewhere).
  useEffect(() => {
    setAgentId(filters.agent_id || '');
    setTestCaseId(filters.test_case_id || '');
    setLimit(filters.limit || '');
  }, [filters.agent_id, filters.test_case_id, filters.limit]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (onFilterChange) {
      onFilterChange({
        agent_id: agentId.trim(),
        test_case_id: testCaseId.trim(),
        limit: limit ? Number(limit) : '',
      });
    }
  };

  const handleReset = () => {
    setAgentId('');
    setTestCaseId('');
    setLimit('');
    if (onReset) {
      onReset();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="filter-bar">
      <div className="filter-field" style={{ flex: '1 1 200px' }}>
        <label htmlFor="agent_id_input">Agent ID</label>
        <input
          id="agent_id_input"
          type="text"
          className="input"
          placeholder="e.g. agent_v1"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
        />
      </div>

      <div className="filter-field" style={{ flex: '1 1 200px' }}>
        <label htmlFor="test_case_id_input">Test Case ID</label>
        <input
          id="test_case_id_input"
          type="text"
          className="input"
          placeholder="e.g. test_001"
          value={testCaseId}
          onChange={(e) => setTestCaseId(e.target.value)}
        />
      </div>

      <div className="filter-field" style={{ width: '120px' }}>
        <label htmlFor="limit_input">Limit</label>
        <input
          id="limit_input"
          type="number"
          min="1"
          className="input"
          placeholder="e.g. 10"
          value={limit}
          onChange={(e) => setLimit(e.target.value)}
        />
      </div>

      <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
        <button type="submit" className="btn btn--primary">
          Apply Filters
        </button>
        <button type="button" onClick={handleReset} className="btn btn--secondary">
          Reset
        </button>
      </div>
    </form>
  );
};

export default FilterBar;
