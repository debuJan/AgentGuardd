import React, { useState, useEffect } from 'react';
import { getSettings, saveSettings } from '../utils/settingsStorage';

export default function SettingsView() {
  const [settings, setSettings] = useState(getSettings());
  const [savedMessage, setSavedMessage] = useState('');

  // Synchronize state if settings are changed elsewhere
  useEffect(() => {
    const handleStorageChange = () => {
      setSettings(getSettings());
    };
    window.addEventListener('settingsUpdated', handleStorageChange);
    return () => window.removeEventListener('settingsUpdated', handleStorageChange);
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setSettings((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    saveSettings(settings);
    setSavedMessage('Settings saved successfully!');
    setTimeout(() => setSavedMessage(''), 3000);
  };

  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h2 className="panel__title">Settings</h2>
          <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#94A3B8' }}>
            Platform configuration and environment information
          </p>
        </div>
      </div>

      {savedMessage && (
        <div style={{ padding: '8px 12px', marginBottom: '12px', backgroundColor: '#10B98122', border: '1px solid #10B981', borderRadius: '6px', color: '#10B981', fontSize: '0.85rem' }}>
          {savedMessage}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '16px' }}>
        {/* Editable Threshold Settings */}
        <div style={{ display: 'grid', gap: '12px' }}>
          <div className="settings-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>Enable Alerts</strong>
            <input
              type="checkbox"
              name="enableAlerts"
              checked={settings.enableAlerts ?? true}
              onChange={handleChange}
            />
          </div>

          <div className="settings-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>Risk Score Threshold (0-100)</strong>
            <input
              type="number"
              name="alertThreshold"
              min="0"
              max="100"
              value={settings.alertThreshold ?? 70}
              onChange={handleChange}
              style={{ width: '80px', padding: '4px 8px', borderRadius: '4px', border: '1px solid #334155', background: '#0F172A', color: '#FFF' }}
            />
          </div>
        </div>

        <div>
          <button
            type="submit"
            style={{ padding: '8px 16px', borderRadius: '6px', backgroundColor: '#3B82F6', color: '#FFF', border: 'none', cursor: 'pointer' }}
          >
            Save Settings
          </button>
        </div>
      </form>

      <hr style={{ margin: '20px 0', borderColor: '#334155' }} />

      {/* Existing Read-only System Information */}
      <div style={{ display: 'grid', gap: '12px' }}>
        <div className="settings-card">
          <strong>API Base URL</strong>
          <span>{import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}</span>
        </div>

        <div className="settings-card">
          <strong>Environment</strong>
          <span>{import.meta.env.MODE}</span>
        </div>

        <div className="settings-card">
          <strong>Platform Version</strong>
          <span>v1.0</span>
        </div>

        <div className="settings-card">
          <strong>Frontend</strong>
          <span>React + Vite</span>
        </div>

        <div className="settings-card">
          <strong>Backend</strong>
          <span>FastAPI</span>
        </div>
      </div>
    </section>
  );
}