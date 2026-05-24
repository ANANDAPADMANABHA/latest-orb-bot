import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Watchlist
export const getWatchlist = () => api.get('/watchlist/');
export const addTicker = (symbol) => api.post('/watchlist/', { symbol });
export const deleteTicker = (id) => api.delete(`/watchlist/${id}/`);

// Bot control
export const getBotStatus = () => api.get('/bot/status/');
export const startBot = () => api.post('/bot/start/');
export const stopBot = () => api.post('/bot/stop/');

// Live data
export const getPositions = () => api.get('/positions/');
export const getOrders = () => api.get('/orders/');
export const getCapital = () => api.get('/capital/');

// P&L
export const getPnLHistory = (date) => api.get('/pnl/', { params: date ? { date } : {} });
export const getPnLToday = () => api.get('/pnl/today/');
export const getPnLSummary = () => api.get('/pnl/summary/');

// Sessions
export const getSessions = () => api.get('/sessions/');
