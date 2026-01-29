import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Можна додати auth token якщо потрібно
    // const token = localStorage.getItem('token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error('API Error:', error.response.data);
    } else if (error.request) {
      console.error('Network Error:', error.message);
    }
    return Promise.reject(error);
  }
);

// ========== Parsing API ==========

export const parsingAPI = {
  start: (data) => apiClient.post('/parsing/start', data),
  stop: () => apiClient.post('/parsing/stop'),
  status: () => apiClient.get('/parsing/status'),
  progress: (sessionId) => apiClient.get(`/parsing/progress/${sessionId}`),
};

// ========== Configuration API ==========

export const configAPI = {
  get: () => apiClient.get('/config'),
  update: (data) => apiClient.put('/config', data),
  reset: () => apiClient.post('/config/reset'),
  test: (data) => apiClient.post('/config/test', data),
  // Domains management
  uploadDomains: (data) => apiClient.post('/config/domains/upload', data),
  getDomains: () => apiClient.get('/config/domains'),
  clearDomains: () => apiClient.delete('/config/domains'),
};

// ========== Reports API ==========

export const reportsAPI = {
  list: (params) => apiClient.get('/reports', { params }),
  summary: (params) => apiClient.get('/reports/summary', { params }),
  export: (format, params) => 
    apiClient.get('/reports/export', { 
      params: { ...params, format },
      responseType: 'blob'
    }),
};

// ========== Scheduler API ==========

export const schedulerAPI = {
  status: () => apiClient.get('/scheduler/status'),
  start: () => apiClient.post('/scheduler/start'),
  stop: (wait = true) => apiClient.post('/scheduler/stop', null, { params: { wait } }),
  addJob: (data) => apiClient.post('/scheduler/jobs/cron', data),
  removeJob: (jobId) => apiClient.delete(`/scheduler/jobs/${jobId}`),
  pauseJob: (jobId) => apiClient.post(`/scheduler/jobs/${jobId}/pause`),
  resumeJob: (jobId) => apiClient.post(`/scheduler/jobs/${jobId}/resume`),
  getJob: (jobId) => apiClient.get(`/scheduler/jobs/${jobId}`),
  initDefaults: (domains, config) => 
    apiClient.post('/scheduler/init-defaults', { domains, config }),
};

// ========== Logs API ==========

export const logsAPI = {
  get: (params) => apiClient.get('/logs', { params }),
  clear: () => apiClient.delete('/logs'),
  stats: () => apiClient.get('/logs/stats'),
};

// ========== Health Check ==========

export const healthAPI = {
  check: () => apiClient.get('/health', { baseURL: 'http://localhost:8000/api/v1' }),
};

export default apiClient;
