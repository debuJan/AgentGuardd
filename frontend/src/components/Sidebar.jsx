import React from 'react';

const NAV_ITEMS = [
  {
    key: 'dashboard',
    label: 'Dashboard',
    enabled: true,
    icon: (
      <path
        d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"
        fill="currentColor"
      />
    ),
  },
  {
    key: 'runs',
    label: 'Runs',
    enabled: true,
    icon: (
      <path
        d="M13 2L3 14h7l-1 8 10-12h-7l1-8z"
        fill="currentColor"
      />
    ),
  },
  {
    key: 'agents',
    label: 'Agents',
    enabled: true,
    icon: (
      <path
        d="M12 2a5 5 0 100 10 5 5 0 000-10zM4 22c0-4.4 3.6-8 8-8s8 3.6 8 8"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
  {
    key: 'test-cases',
    label: 'Test Cases',
    enabled: true,
    icon: (
      <path
        d="M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
  {
    key: 'reports',
    label: 'Reports',
    enabled: true,
    icon: (
      <path
        d="M4 19h16M6 15h2v4H6zM11 11h2v8h-2zM16 7h2v12h-2z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
  {
    key: 'alerts',
    label: 'Alerts',
    enabled: true,
    icon: (
      <path
        d="M12 22c1.1 0 2-.9 2-2h-4a2 2 0 002 2zm6-6v-5a6 6 0 10-12 0v5l-2 2v1h16v-1l-2-2z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
  {
    key: 'settings',
    label: 'Settings',
    enabled: true,
    icon: (
      <path
        d="M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09a1.65 1.65 0 00-1-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
];

/**
 * Sidebar Component
 */
export const Sidebar = ({ currentView = 'dashboard', onNavigate }) => {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__brand-mark">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M12 2L2 7v6c0 5.25 3.75 9.75 10 11 6.25-1.25 10-5.75 10-11V7l-10-5z"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinejoin="round"
            />
            <path
              d="M9 12l2 2 4-4"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <span className="sidebar__brand-name">AgentGuard</span>
      </div>

      <nav className="sidebar__nav">
        {NAV_ITEMS.map((item) => {
          const isActive = currentView === item.key;

          return (
            <button
              key={item.key}
              type="button"
              onClick={() => item.enabled && onNavigate && onNavigate(item.key)}
              disabled={!item.enabled}
              className={`sidebar__item${isActive ? ' sidebar__item--active' : ''}${
                !item.enabled ? ' sidebar__item--disabled' : ''
              }`}
              style={{
                width: '100%',
                background: 'none',
                border: 'none',
                textAlign: 'left',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                cursor: item.enabled ? 'pointer' : 'not-allowed',
                opacity: item.enabled ? 1 : 0.5,
              }}
              title={item.enabled ? item.label : `${item.label} (coming soon)`}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  {item.icon}
                </svg>
                <span>{item.label}</span>
              </div>

              {!item.enabled && (
                <span
                  style={{
                    fontSize: '0.625rem',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    padding: '2px 5px',
                    borderRadius: '4px',
                    backgroundColor: 'rgba(255, 255, 255, 0.06)',
                    color: '#64748B',
                    letterSpacing: '0.04em',
                  }}
                >
                  Soon
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <div className="sidebar__footer">
        <span>v1.0 &middot; AI Agent Platform</span>
      </div>
    </aside>
  );
};

export default Sidebar;