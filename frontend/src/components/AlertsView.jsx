import React, { useState, useEffect } from 'react';
import { getSettings } from '../utils/settingsStorage';

export default function AlertsView({ alerts = [] }) {
  const [settings, setSettings] = useState(getSettings());

  useEffect(() => {
    const handleSettingsUpdate = () => {
      setSettings(getSettings());
    };

    window.addEventListener('settingsUpdated', handleSettingsUpdate);
    return () => window.removeEventListener('settingsUpdated', handleSettingsUpdate);
  }, []);

  const threshold = Number(settings.alertThreshold ?? 70);
  const alertsEnabled = settings.enableAlerts ?? true;

  // Filter alerts matching the risk threshold
  const filteredAlerts = alerts.filter(
    (alert) => (alert.riskScore ?? 0) >= threshold
  );

  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h2 className="panel__title">Alerts</h2>
          <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#94A3B8' }}>
            Active risk &amp; policy failure events meeting risk threshold (&ge; {threshold})
          </p>
        </div>
        <span className="panel__count">{alertsEnabled ? filteredAlerts.length : 0}</span>
      </div>

      {!alertsEnabled ? (
        <div className="state-block">
          <span style={{ color: '#F59E0B' }}>
            Alert notifications are currently disabled in Settings.
          </span>
        </div>
      ) : filteredAlerts.length === 0 ? (
        <div className="state-block">
          <span>No active alerts above the current risk threshold of {threshold}.</span>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '12px' }}>
          {filteredAlerts.map((alert, index) => (
            <div
              key={alert.id || index}
              data-testid="alert-item"
              style={{
                padding: '16px',
                background: 'rgba(127, 29, 29, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                borderLeft: '4px solid #EF4444',
                borderRadius: '8px',
                display: 'flex',
                justify: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <strong style={{ color: '#F8FAFC', fontSize: '0.95rem' }}>
                  {alert.name || alert.id}
                </strong>
                <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#CBD5E1' }}>
                  {alert.message}
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.2)',
                    color: '#EF4444',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    fontWeight: 700,
                    fontSize: '0.8rem',
                  }}
                >
                  Risk: {alert.severity || 'N/A'} ({alert.riskScore})
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}