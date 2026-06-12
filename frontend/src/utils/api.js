// frontend/src/utils/api.js
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token if present
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('skyaudit_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('skyaudit_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export const schoolsApi = {
  getProfile: (udise) => api.get(`/schools/${udise}`),
  getSatellite: (udise) => api.get(`/schools/${udise}/satellite`),
  getVerifications: (udise) => api.get(`/schools/${udise}/verification`),
  flagSchool: (udise, data) => api.post(`/schools/${udise}/flag`, data),
};

export const districtsApi = {
  getProfile: (code) => api.get(`/districts/${code}`),
  getSchools: (code, params) => api.get(`/districts/${code}/schools`, { params }),
  getAnomalies: (code, params) => api.get(`/districts/${code}/anomalies`, { params }),
  getRankings: (params) => api.get('/districts/rankings', { params }),
};

export const anomaliesApi = {
  getOne: (id) => api.get(`/anomalies/${id}`),
  getAll: (params) => api.get('/anomalies/', { params }),
  updateStatus: (id, data) => api.patch(`/anomalies/${id}/status`, data),
};

export const pulseApi = {
  getEvents: (params) => api.get('/pulse/', { params }),
  streamUrl: (params) => {
    const qs = new URLSearchParams(params).toString();
    return `${API_BASE}/pulse/stream${qs ? '?' + qs : ''}`;
  },
};

export const reportsApi = {
  getNationalSummary: () => api.get('/reports/national/summary'),
  getWeekly: (stateCode) => api.get(`/reports/weekly/${stateCode}`),
};

export const authApi = {
  login: (email, password) =>
    api.post('/auth/login', new URLSearchParams({ username: email, password }), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),
  getMe: () => api.get('/auth/me'),
};

export default api;
