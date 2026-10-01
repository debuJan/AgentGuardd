const SETTINGS_KEY = 'agentguard_settings';

export const DEFAULT_SETTINGS = {
  environment: 'development',
  autoRefresh: false,
  refreshInterval: 30, // seconds
  reliabilityThreshold: 80, // %
  securityThreshold: 80, // %
  alertSecurityFailures: true,
  alertReliabilityFailures: true,
  alertCriticalFindings: true,
};

export const getSettings = () => {
  try {
    const saved = localStorage.getItem(SETTINGS_KEY);
    if (saved) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
    }
  } catch (e) {
    console.error('Failed to read settings from localStorage:', e);
  }
  return DEFAULT_SETTINGS;
};

export const saveSettings = (newSettings) => {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(newSettings));
  } catch (e) {
    console.error('Failed to save settings to localStorage:', e);
  }
};