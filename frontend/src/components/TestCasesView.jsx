import React, { useEffect, useState } from 'react';
import { api } from '../api/client';

const CATEGORY_STYLES = {
  security: { color: '#F59E0B', background: 'rgba(245, 158, 11, 0.12)', label: 'Security' },
  reliability: { color: '#10B981', background: 'rgba(16, 185, 129, 0.12)', label: 'Reliability' },
  functional: { color: '#60A5FA', background: 'rgba(96, 165, 250, 0.12)', label: 'Functional' },
};

const inputStyle = {
  width: '100%',
  background: '#1E293B',
  border: '1px solid #334155',
  borderRadius: '6px',
  color: '#F8FAFC',
  padding: '10px 12px',
  fontSize: '0.85rem',
  boxSizing: 'border-box',
};

const labelStyle = {
  display: 'block',
  fontSize: '0.75rem',
  fontWeight: 600,
  color: '#94A3B8',
  marginBottom: '6px',
  marginTop: '14px',
};

const primaryButtonStyle = {
  background: '#7C3AED',
  border: '1px solid #8B5CF6',
  borderRadius: '6px',
  color: '#FFFFFF',
  padding: '8px 14px',
  fontSize: '0.8rem',
  fontWeight: 600,
  cursor: 'pointer',
};

const ghostButtonStyle = {
  background: 'transparent',
  border: '1px solid #475569',
  borderRadius: '6px',
  color: '#CBD5E1',
  padding: '8px 14px',
  fontSize: '0.8rem',
  fontWeight: 600,
  cursor: 'pointer',
};

const dangerButtonStyle = {
  ...ghostButtonStyle,
  border: '1px solid rgba(239, 68, 68, 0.4)',
  color: '#F87171',
};

function categoryBadge(category) {
  const style = CATEGORY_STYLES[category] || CATEGORY_STYLES.functional;
  return (
    <span
      style={{
        padding: '4px 8px',
        borderRadius: '4px',
        fontSize: '0.7rem',
        fontWeight: 700,
        color: style.color,
        background: style.background,
      }}
    >
      {style.label}
    </span>
  );
}

export default function TestCasesView() {
  const [testCases, setTestCases] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState('');

  const [selectedTestCase, setSelectedTestCase] = useState(null);
  const [agentName, setAgentName] = useState('Mock External Agent');
  const [endpointUrl, setEndpointUrl] = useState('http://host.docker.internal:9000/agent');
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [runError, setRunError] = useState('');

  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [form, setForm] = useState({
    title: '',
    category: 'reliability',
    user_input: '',
    expected_tools: '',
    expected_outcome: '',
    agent_name: '',
  });

  const fetchTestCases = async () => {
    setLoadingList(true);
    setListError('');
    try {
      const response = await api.listTestCases();
      setTestCases(response.test_cases || []);
    } catch (err) {
      setListError(err?.message || 'Failed to load test cases.');
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    fetchTestCases();
  }, []);

  const openRunDialog = (testCase) => {
    setSelectedTestCase(testCase);
    setRunResult(null);
    setRunError('');
  };

  const closeRunDialog = () => {
    if (!running) {
      setSelectedTestCase(null);
      setRunError('');
    }
  };

  const buildAgentConfig = (testCase) => {
    const toolNames = (testCase.expected_tool_calls || []).map((c) => c.tool);
    const tools = toolNames.map((toolName) => ({
      name: toolName,
      description: `${toolName} tool`,
      parameters: [],
      is_sensitive: false,
    }));
    return {
      name: agentName.trim(),
      description: 'External AI agent evaluated by AgentGuard',
      execution_type: 'external',
      adapter_type: 'http',
      endpoint_url: endpointUrl.trim(),
      timeout_seconds: 30,
      tools,
      permissions: {
        allowed_tools: toolNames,
        blocked_tools: [],
      },
      policies: [],
      llm: {
        provider: 'groq',
        model: 'llama-3.1-8b-instant',
        temperature: 0,
        max_tokens: 1000,
      },
    };
  };

  const handleRunEvaluation = async () => {
    if (!selectedTestCase) return;
    if (!agentName.trim()) {
      setRunError('Agent name is required.');
      return;
    }
    if (!endpointUrl.trim()) {
      setRunError('External agent endpoint is required.');
      return;
    }
    setRunning(true);
    setRunError('');
    setRunResult(null);
    try {
      // The stored test case is already a valid TestCase: pass it through.
      // (test_case_id could be used instead; inline keeps the run self-contained.)
      const response = await api.createRun({
        agent_config: buildAgentConfig(selectedTestCase),
        test_case: selectedTestCase,
      });
      setRunResult(response);
    } catch (err) {
      setRunError(err?.message || 'Failed to run evaluation.');
    } finally {
      setRunning(false);
    }
  };

  const handleCreate = async () => {
    if (!form.user_input.trim()) {
      setCreateError('Test input is required.');
      return;
    }
    setCreating(true);
    setCreateError('');
    try {
      const toolNames = form.expected_tools
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);
      await api.createTestCase({
        title: form.title.trim() || undefined,
        agent_name: form.agent_name.trim() || 'unspecified',
        category: form.category,
        user_input: form.user_input.trim(),
        expected_tool_calls: toolNames.map((tool, index) => ({
          tool,
          arguments: {},
          order: index + 1,
        })),
        expected_outcome: form.expected_outcome.trim() || undefined,
      });
      setShowCreate(false);
      setForm({
        title: '',
        category: 'reliability',
        user_input: '',
        expected_tools: '',
        expected_outcome: '',
        agent_name: '',
      });
      await fetchTestCases();
    } catch (err) {
      setCreateError(err?.message || 'Failed to create test case.');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (testCase) => {
    if (!window.confirm(`Delete test case "${testCase.title || testCase.id}"?`)) return;
    try {
      await api.deleteTestCase(testCase.id);
      await fetchTestCases();
    } catch (err) {
      setListError(err?.message || 'Failed to delete test case.');
    }
  };

  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h2 className="panel__title">Test Cases</h2>
          <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#94A3B8' }}>
            Reusable evaluation library — reliability and security scenarios
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className="panel__count">{testCases.length}</span>
          <button onClick={() => setShowCreate(true)} style={primaryButtonStyle}>
            + New Test Case
          </button>
        </div>
      </div>

      {loadingList && <p style={{ color: '#94A3B8' }}>Loading test cases…</p>}
      {listError && <p style={{ color: '#F87171' }}>{listError}</p>}

      {!loadingList && !listError && testCases.length === 0 && (
        <div
          style={{
            padding: '32px',
            textAlign: 'center',
            color: '#94A3B8',
            background: 'rgba(30, 41, 59, 0.4)',
            border: '1px dashed #334155',
            borderRadius: '8px',
          }}
        >
          <p style={{ margin: '0 0 8px', color: '#F8FAFC', fontWeight: 600 }}>
            No test cases yet
          </p>
          <p style={{ margin: 0, fontSize: '0.85rem' }}>
            Create one above, or seed the demo library with{' '}
            <code>python scripts/seed_demo_test_cases.py</code>.
          </p>
        </div>
      )}

      <div style={{ display: 'grid', gap: '12px' }}>
        {testCases.map((testCase) => {
          const toolNames = (testCase.expected_tool_calls || []).map((c) => c.tool);
          return (
            <div
              key={testCase.id}
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
                  marginBottom: '8px',
                }}
              >
                <div>
                  <strong style={{ color: '#F8FAFC' }}>
                    {testCase.title || testCase.id}
                  </strong>
                  <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '3px' }}>
                    {testCase.id}
                  </div>
                </div>
                {categoryBadge(testCase.category)}
              </div>

              <div style={{ fontSize: '0.8rem', color: '#CBD5E1', marginBottom: '10px' }}>
                <strong>Input:</strong> {testCase.user_input}
              </div>

              {toolNames.length > 0 && (
                <div style={{ fontSize: '0.8rem', color: '#94A3B8' }}>
                  <strong>Expected tools:</strong> {toolNames.join(' → ')}
                </div>
              )}

              {testCase.expected_outcome && (
                <div style={{ fontSize: '0.8rem', color: '#94A3B8', marginTop: '5px' }}>
                  <strong>Expected outcome:</strong> {testCase.expected_outcome}
                </div>
              )}

              <div style={{ display: 'flex', gap: '8px', marginTop: '14px' }}>
                <button onClick={() => openRunDialog(testCase)} style={primaryButtonStyle}>
                  Run Evaluation
                </button>
                <button onClick={() => handleDelete(testCase)} style={dangerButtonStyle}>
                  Delete
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {showCreate && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.65)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: '20px',
          }}
        >
          <div
            style={{
              width: '100%', maxWidth: '560px', maxHeight: '90vh', overflowY: 'auto',
              background: '#0F172A', border: '1px solid #334155',
              borderRadius: '10px', padding: '24px',
              boxShadow: '0 20px 50px rgba(0, 0, 0, 0.4)',
            }}
          >
            <h3 style={{ margin: '0 0 4px', color: '#F8FAFC', fontSize: '1.1rem' }}>
              New Test Case
            </h3>
            <p style={{ margin: '0', color: '#94A3B8', fontSize: '0.8rem' }}>
              Saved to the library and reusable across runs.
            </p>

            <label style={labelStyle}>Title</label>
            <input
              style={inputStyle}
              placeholder="e.g. Delivery - Happy Path"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />

            <label style={labelStyle}>Category</label>
            <select
              style={inputStyle}
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            >
              <option value="reliability">Reliability — can the agent do its job?</option>
              <option value="security">Security — does it resist abuse?</option>
              <option value="functional">Functional — does the feature work?</option>
            </select>

            <label style={labelStyle}>Test input</label>
            <textarea
              style={{ ...inputStyle, minHeight: '70px', resize: 'vertical' }}
              placeholder="e.g. Where is my order #5678?"
              value={form.user_input}
              onChange={(e) => setForm({ ...form, user_input: e.target.value })}
            />

            <label style={labelStyle}>Expected tools (comma-separated, in order)</label>
            <input
              style={inputStyle}
              placeholder="e.g. get_order, track_shipment"
              value={form.expected_tools}
              onChange={(e) => setForm({ ...form, expected_tools: e.target.value })}
            />

            <label style={labelStyle}>Expected outcome</label>
            <input
              style={inputStyle}
              placeholder="e.g. The agent returns the tracking status."
              value={form.expected_outcome}
              onChange={(e) => setForm({ ...form, expected_outcome: e.target.value })}
            />

            {createError && (
              <p style={{ color: '#F87171', fontSize: '0.85rem' }}>{createError}</p>
            )}

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '20px' }}>
              <button
                onClick={() => !creating && setShowCreate(false)}
                style={ghostButtonStyle}
              >
                Cancel
              </button>
              <button onClick={handleCreate} disabled={creating} style={primaryButtonStyle}>
                {creating ? 'Creating…' : 'Create Test Case'}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedTestCase && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0, 0, 0, 0.65)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: '20px',
          }}
        >
          <div
            style={{
              width: '100%', maxWidth: '560px',
              background: '#0F172A', border: '1px solid #334155',
              borderRadius: '10px', padding: '24px',
              boxShadow: '0 20px 50px rgba(0, 0, 0, 0.4)',
            }}
          >
            <div
              style={{
                display: 'flex', justifyContent: 'space-between',
                alignItems: 'center', marginBottom: '20px',
              }}
            >
              <div>
                <h3 style={{ margin: 0, color: '#F8FAFC', fontSize: '1.1rem' }}>
                  Run Evaluation
                </h3>
                <p style={{ margin: '5px 0 0', color: '#94A3B8', fontSize: '0.8rem' }}>
                  {selectedTestCase.title || selectedTestCase.id}
                </p>
              </div>
              <button
                onClick={closeRunDialog}
                style={{
                  background: 'transparent', border: 'none', color: '#94A3B8',
                  fontSize: '1.2rem', cursor: 'pointer',
                }}
              >
                ×
              </button>
            </div>

            <label style={{ ...labelStyle, marginTop: 0 }}>Agent Name</label>
            <input
              style={inputStyle}
              value={agentName}
              onChange={(e) => setAgentName(e.target.value)}
            />

            <label style={labelStyle}>External Agent Endpoint</label>
            <input
              style={inputStyle}
              value={endpointUrl}
              onChange={(e) => setEndpointUrl(e.target.value)}
            />

            {runError && (
              <p style={{ color: '#F87171', fontSize: '0.85rem' }}>{runError}</p>
            )}
            {runResult && (
              <p style={{ color: '#10B981', fontSize: '0.85rem' }}>
                Run complete — report <strong>{runResult.run_id}</strong> is now
                in the Runs list.
              </p>
            )}

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '20px' }}>
              <button onClick={closeRunDialog} style={ghostButtonStyle}>
                Cancel
              </button>
              <button
                onClick={handleRunEvaluation}
                disabled={running}
                style={primaryButtonStyle}
              >
                {running ? 'Running…' : 'Run Evaluation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
