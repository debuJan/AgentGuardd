import React, { useMemo, useState } from 'react';

const AgentsView = ({
  reports = [],
  loading = false,
  onRefresh,
  onSelectRun,
  onNavigate,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  // Score extraction & normalization (0-100 scale)
  const extractNormalizedScore = (scoreVal) => {
    if (scoreVal === undefined || scoreVal === null || scoreVal === '') return null;
    const num = Number(scoreVal);
    if (isNaN(num)) return null;
    return num <= 1 && num > 0 ? num * 100 : num;
  };

  // Pass status check
  const isPassStatus = (statusStr) => {
    if (!statusStr) return false;
    const s = String(statusStr).toUpperCase().trim();
    return s === 'PASS' || s === 'PASSED' || s === 'SUCCESS';
  };

  // Group reports by agent_id
  const agentStats = useMemo(() => {
    const map = {};

    reports.forEach((run) => {
      const agentId = run.agent_id ? String(run.agent_id) : 'Unknown Agent';

      if (!map[agentId]) {
        map[agentId] = {
          id: agentId,
          name: agentId,
          totalRuns: 0,
          passedRuns: 0,
          totalScore: 0,
          scoredRunsCount: 0,
          totalReliability: 0,
          reliabilityCount: 0,
          totalSecurity: 0,
          securityCount: 0,
          lastRunDate: null,
          runs: [],
        };
      }

      const agent = map[agentId];
      agent.totalRuns += 1;
      agent.runs.push(run);

      // Overall status
      const rawStatus = run.overall_status ?? run.status;
      if (isPassStatus(rawStatus)) {
        agent.passedRuns += 1;
      }

      // Overall Score
      const rawScore =
        run.overall_score ??
        run.score ??
        run.metrics?.overall_score ??
        run.metrics?.score;
      const score = extractNormalizedScore(rawScore);
      if (score !== null) {
        agent.totalScore += score;
        agent.scoredRunsCount += 1;
      }

      // Reliability Score
      const rawRel =
        run.reliability?.reliability_score ??
        run.reliability_score ??
        run.metrics?.reliability;
      const relScore = extractNormalizedScore(rawRel);
      if (relScore !== null) {
        agent.totalReliability += relScore;
        agent.reliabilityCount += 1;
      }

      // Security Score
      const rawSec =
        run.security?.security_score ??
        run.security_score ??
        run.metrics?.security;
      const secScore = extractNormalizedScore(rawSec);
      if (secScore !== null) {
        agent.totalSecurity += secScore;
        agent.securityCount += 1;
      }

      // Last run timestamp
      const runDate = run.timestamp || run.created_at || run.date;
      if (runDate) {
        const d = new Date(runDate);
        if (!isNaN(d.getTime())) {
          if (!agent.lastRunDate || d > agent.lastRunDate) {
            agent.lastRunDate = d;
          }
        }
      }
    });

    return Object.values(map).map((agent) => {
      const avgScore =
        agent.scoredRunsCount > 0
          ? Math.round(agent.totalScore / agent.scoredRunsCount)
          : 0;

      const avgReliability =
        agent.reliabilityCount > 0
          ? Math.round(agent.totalReliability / agent.reliabilityCount)
          : 0;

      const avgSecurity =
        agent.securityCount > 0
          ? Math.round(agent.totalSecurity / agent.securityCount)
          : 0;

      const passRate =
        agent.totalRuns > 0
          ? Math.round((agent.passedRuns / agent.totalRuns) * 100)
          : 0;

      let healthStatus = 'Healthy';
      let healthColor = '#34D399';
      let healthBg = 'rgba(52, 211, 153, 0.15)';
      let healthBorder = 'rgba(52, 211, 153, 0.3)';

      if (passRate < 60 || avgScore < 60) {
        healthStatus = 'Needs Attention';
        healthColor = '#EF4444';
        healthBg = 'rgba(239, 68, 68, 0.15)';
        healthBorder = 'rgba(239, 68, 68, 0.3)';
      } else if (passRate < 85 || avgScore < 80) {
        healthStatus = 'Warning';
        healthColor = '#FBBF24';
        healthBg = 'rgba(251, 191, 36, 0.15)';
        healthBorder = 'rgba(251, 191, 36, 0.3)';
      }

      return {
        ...agent,
        avgScore,
        avgReliability,
        avgSecurity,
        passRate,
        healthStatus,
        healthColor,
        healthBg,
        healthBorder,
      };
    });
  }, [reports]);

  // Filter logic
  const filteredAgents = useMemo(() => {
    return agentStats.filter((agent) => {
      const matchesSearch = agent.name
        .toLowerCase()
        .includes(searchTerm.toLowerCase());

      if (!matchesSearch) return false;

      if (statusFilter === 'HEALTHY') return agent.healthStatus === 'Healthy';
      if (statusFilter === 'WARNING') return agent.healthStatus === 'Warning';
      if (statusFilter === 'NEEDS_ATTENTION') return agent.healthStatus === 'Needs Attention';

      return true;
    });
  }, [agentStats, searchTerm, statusFilter]);

  // Overall metrics summary
  const overallMetrics = useMemo(() => {
    const totalAgents = agentStats.length;
    const agentsWithRuns = agentStats.filter((a) => a.totalRuns > 0).length;

    if (totalAgents === 0) {
      return {
        totalAgents: 0,
        agentsWithRuns: 0,
        avgScore: 0,
        avgPassRate: 0,
        totalRuns: 0,
      };
    }

    const totalRuns = agentStats.reduce((acc, a) => acc + a.totalRuns, 0);
    const sumScores = agentStats.reduce((acc, a) => acc + a.avgScore, 0);
    const sumPassRates = agentStats.reduce((acc, a) => acc + a.passRate, 0);

    return {
      totalAgents,
      agentsWithRuns,
      totalRuns,
      avgScore: Math.round(sumScores / totalAgents),
      avgPassRate: Math.round(sumPassRates / totalAgents),
    };
  }, [agentStats]);

  const handleViewRuns = (agentId) => {
    if (onNavigate) {
      onNavigate('runs', { agentId });
    } else if (onSelectRun) {
      const agentObj = agentStats.find((a) => a.id === agentId);
      if (agentObj && agentObj.runs.length > 0) {
        onSelectRun(agentObj.runs[0].run_id || agentObj.runs[0].id);
      }
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* 1. Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0, color: '#F8FAFC' }}>Agents</h1>
          <p style={{ margin: '4px 0 0', color: '#94A3B8', fontSize: '0.9rem' }}>
            Monitor and analyze AI agent performance across execution runs
          </p>
        </div>
      </div>

      {/* 2. Summary Metrics KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        <div style={{ background: '#1E293B', border: '1px solid #334155', borderRadius: '8px', padding: '16px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase' }}>Total Agents</span>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#F8FAFC', margin: '8px 0 4px' }}>{overallMetrics.totalAgents}</div>
          <span style={{ fontSize: '0.8rem', color: '#64748B' }}>{overallMetrics.agentsWithRuns} with recorded runs</span>
        </div>

        <div style={{ background: '#1E293B', border: '1px solid #334155', borderRadius: '8px', padding: '16px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase' }}>Total Runs</span>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#F8FAFC', margin: '8px 0 4px' }}>{overallMetrics.totalRuns}</div>
          <span style={{ fontSize: '0.8rem', color: '#64748B' }}>across all agent reports</span>
        </div>

        <div style={{ background: '#1E293B', border: '1px solid #334155', borderRadius: '8px', padding: '16px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase' }}>Avg Score</span>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#38BDF8', margin: '8px 0 4px' }}>{overallMetrics.avgScore}%</div>
          <span style={{ fontSize: '0.8rem', color: '#64748B' }}>aggregated evaluation score</span>
        </div>

        <div style={{ background: '#1E293B', border: '1px solid #334155', borderRadius: '8px', padding: '16px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase' }}>Avg Pass Rate</span>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: '#34D399', margin: '8px 0 4px' }}>{overallMetrics.avgPassRate}%</div>
          <span style={{ fontSize: '0.8rem', color: '#64748B' }}>overall test case success rate</span>
        </div>
      </div>

      {/* 3. Filter Toolbar */}
      <div style={{ background: '#1E293B', border: '1px solid #334155', borderRadius: '8px', padding: '16px', display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="Search agents by agent_id..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            flex: 1,
            minWidth: '220px',
            background: '#0F172A',
            border: '1px solid #334155',
            borderRadius: '6px',
            padding: '8px 12px',
            color: '#F8FAFC',
            fontSize: '0.875rem',
            outline: 'none'
          }}
        />

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{
            background: '#0F172A',
            border: '1px solid #334155',
            borderRadius: '6px',
            padding: '8px 12px',
            color: '#F8FAFC',
            fontSize: '0.875rem',
            outline: 'none',
            cursor: 'pointer'
          }}
        >
          <option value="ALL">All Health Statuses</option>
          <option value="HEALTHY">Healthy</option>
          <option value="WARNING">Warning</option>
          <option value="NEEDS_ATTENTION">Needs Attention</option>
        </select>

        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={loading}
            style={{
              background: '#0F172A',
              border: '1px solid #334155',
              borderRadius: '6px',
              padding: '8px 14px',
              color: '#F8FAFC',
              fontSize: '0.85rem',
              cursor: 'pointer'
            }}
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        )}
      </div>

      {/* 4. Agents List Rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {filteredAgents.length === 0 ? (
          <div className="state-block" style={{ background: '#1E293B', border: '1px solid #334155', borderRadius: '8px', padding: '32px', textAlign: 'center', color: '#94A3B8' }}>
            <span>No agent records match your filter parameters.</span>
          </div>
        ) : (
          filteredAgents.map((agent) => (
            <div
              key={agent.id}
              style={{
                background: '#1E293B',
                border: '1px solid #334155',
                borderRadius: '8px',
                padding: '20px',
                display: 'flex',
                alignItems: 'center',
                justify: 'space-between',
                gap: '20px',
                flexWrap: 'wrap'
              }}
            >
              {/* Left Column: Identifier + Status */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '14px', minWidth: '240px' }}>
                <div style={{
                  width: '42px',
                  height: '42px',
                  borderRadius: '8px',
                  background: 'rgba(124, 58, 237, 0.15)',
                  border: '1px solid rgba(124, 58, 237, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  justify: 'center',
                  fontSize: '1.2rem',
                  flexShrink: 0
                }}>
                  🤖
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ color: '#F8FAFC', fontWeight: 600, fontSize: '1rem', lineHeight: '1.2' }}>{agent.name}</div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <span style={{
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      backgroundColor: agent.healthBg,
                      color: agent.healthColor,
                      border: `1px solid ${agent.healthBorder}`,
                      whiteSpace: 'nowrap'
                    }}>
                      {agent.healthStatus}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: '#64748B', whiteSpace: 'nowrap' }}>
                      {agent.totalRuns > 0
                        ? agent.lastRunDate
                          ? `Last run: ${agent.lastRunDate.toLocaleDateString()}`
                          : `Recorded runs (${agent.totalRuns})`
                        : 'No runs recorded yet'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Center Metrics Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(65px, 1fr))', gap: '16px', flex: 1, minWidth: '320px', textAlign: 'center' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500 }}>Total Runs</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#F8FAFC', marginTop: '4px' }}>{agent.totalRuns}</div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500 }}>Avg Score</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#38BDF8', marginTop: '4px' }}>{agent.avgScore}%</div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500 }}>Pass Rate</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#34D399', marginTop: '4px' }}>{agent.passRate}%</div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500 }}>Reliability</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#A78BFA', marginTop: '4px' }}>{agent.avgReliability}%</div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500 }}>Security</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#F472B6', marginTop: '4px' }}>{agent.avgSecurity}%</div>
                </div>
              </div>

              {/* Right Action Button */}
              <div>
                <button
                  onClick={() => handleViewRuns(agent.id)}
                  style={{
                    background: 'transparent',
                    border: '1px solid #475569',
                    borderRadius: '6px',
                    color: '#F8FAFC',
                    padding: '8px 14px',
                    fontSize: '0.85rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap'
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.background = '#334155';
                    e.currentTarget.style.borderColor = '#64748B';
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.borderColor = '#475569';
                  }}
                >
                  View Runs &rarr;
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default AgentsView;