/**
 * API Client for AI Agent Reliability & Security Platform
 * Wraps native fetch calls to interact with FastAPI endpoints.
 */

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = { detail: response.statusText };
      }

      throw new ApiError(
        errorData.detail || `Request failed with status ${response.status}`,
        response.status,
        errorData
      );
    }

    // For 204 No Content
    if (response.status === 204) {
      return null;
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    throw new ApiError(
      error.message || 'Network error occurred',
      0,
      null
    );
  }
}

export const api = {
  /**
   * Health check endpoint
   */
  async checkHealth() {
    return request('/health');
  },

  /**
   * Run an agent evaluation
   * @param {Object} payload - Agent configuration and test case
   */
  async createRun(payload) {
    return request('/runs', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Fetch all run reports with optional filters
   * @param {Object} filters - { agent_id, test_case_id, limit }
   */
  async listRuns(filters = {}) {
    const params = new URLSearchParams();

    if (filters.agent_id) {
      params.append('agent_id', filters.agent_id);
    }

    if (filters.test_case_id) {
      params.append('test_case_id', filters.test_case_id);
    }

    if (filters.limit) {
      params.append('limit', filters.limit);
    }

    const queryString = params.toString();
    const endpoint = `/runs${queryString ? `?${queryString}` : ''}`;

    return request(endpoint);
  },

  /**
   * Fetch a single detailed report by run_id
   * @param {string} runId
   */
  async getRunDetails(runId) {
    return request(`/runs/${encodeURIComponent(runId)}`);
  },

  /**
   * Delete a run report by run_id
   * @param {string} runId
   */
  async deleteRun(runId) {
    return request(`/runs/${encodeURIComponent(runId)}`, {
      method: 'DELETE',
    });
  },

  /**
   * List stored test cases (the reusable evaluation library)
   * @param {Object} filters - { category, limit }
   */
  async listTestCases(filters = {}) {
    const params = new URLSearchParams();

    if (filters.category) {
      params.append('category', filters.category);
    }

    if (filters.limit) {
      params.append('limit', filters.limit);
    }

    const queryString = params.toString();
    const endpoint = `/test-cases${queryString ? `?${queryString}` : ''}`;

    return request(endpoint);
  },

  /**
   * Fetch a single test case by id
   * @param {string} testCaseId
   */
  async getTestCase(testCaseId) {
    return request(`/test-cases/${encodeURIComponent(testCaseId)}`);
  },

  /**
   * Create a test case in the library
   * @param {Object} payload - TestCaseCreate fields; id is optional
   */
  async createTestCase(payload) {
    return request('/test-cases', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  /**
   * Delete a test case by id
   * @param {string} testCaseId
   */
  async deleteTestCase(testCaseId) {
    return request(`/test-cases/${encodeURIComponent(testCaseId)}`, {
      method: 'DELETE',
    });
  },
};