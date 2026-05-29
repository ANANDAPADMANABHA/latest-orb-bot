import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

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
export const getPositions = () => api.get('/positions/');
export const getOrders = () => api.get('/orders/');
export const getCapital = () => api.get('/capital/');

// P&L
export const getPnLHistory = (date) => api.get('/pnl/', { params: date ? { date } : {} });
export const getPnLToday = () => api.get('/pnl/today/');
export const getPnLSummary = () => api.get('/pnl/summary/');

// Sessions
export const getSessions = () => api.get('/sessions/');
