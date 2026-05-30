import axios from 'axios';

function getCookie(name) {
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? decodeURIComponent(match[2]) : null;
}

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase();
  if (method && ['post', 'put', 'patch', 'delete'].includes(method)) {
    const csrfToken = getCookie('csrftoken');
    if (csrfToken) {
      config.headers['X-CSRFToken'] = csrfToken;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginRequest = error.config?.url?.includes('/auth/login/');
    const onLoginPage = window.location.pathname === '/login';
    if (error.response?.status === 401 && !isLoginRequest && !onLoginPage) {
      window.location.assign('/login');
    }
    return Promise.reject(error);
  },
);

// Auth
export const fetchCsrf = () => api.get('/auth/csrf/');
export const login = (username, password) =>
  api.post('/auth/login/', { username, password });
export const logout = () => api.post('/auth/logout/');
export const getMe = () => api.get('/auth/me/');

// Watchlist
export const getWatchlist = () => api.get('/watchlist/');
export const addTicker = (symbol) => api.post('/watchlist/', { symbol });
export const deleteTicker = (id) => api.delete(`/watchlist/${id}/`);

// Charts (forceRefresh bypasses 60s server cache)
export const getWatchlistCharts = (forceRefresh = false) =>
  api.get('/charts/watchlist/', {
    params: forceRefresh ? { refresh: 1 } : {},
  });

// Dashboard ORB gauge (ORB high/low + last price, no candles)
export const getOrbWatchlist = (forceRefresh = false) =>
  api.get('/orb/watchlist/', {
    params: forceRefresh ? { refresh: 1 } : {},
  });

// Bot control
export const getBotStatus = () => api.get('/bot/status/');
export const getBotSettings = () => api.get('/bot/settings/');
export const updateBotSettings = (data) => api.patch('/bot/settings/', data);
export const startBot = () => api.post('/bot/start/');
export const stopBot = () => api.post('/bot/stop/');

// Live data (broker/live uses one Angel One login for both)
export const getBrokerLive = () => api.get('/broker/live/');
export const exitPosition = (tradingsymbol) =>
  api.post('/positions/exit/', { tradingsymbol });
export const getPositions = () => api.get('/positions/');
export const getOrders = () => api.get('/orders/');
export const getCapital = () => api.get('/capital/');

// P&L
export const getPnLHistory = (date) => api.get('/pnl/', { params: date ? { date } : {} });
export const syncPnL = () => api.post('/pnl/sync/');
export const getPnLToday = () => api.get('/pnl/today/');
export const getPnLSummary = () => api.get('/pnl/summary/');

// Sessions
export const getSessions = () => api.get('/sessions/');

// System health
export const getSystemHealth = (probe = false) =>
  api.get('/health/', { params: probe ? { probe: 1 } : {} });
