import { useState, useEffect, useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import { getSimTrades, settleSimTrades, getSimSummary } from '../api/client';
import './SimTrades.css';

function formatDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
}

function barColor(pnl) {
  if (pnl > 0) return 'var(--green)';
  if (pnl < 0) return 'var(--red)';
  return 'var(--text-muted)';
}

function addDaysIso(iso, days) {
  const [y, m, d] = iso.split('-').map(Number);
  const next = new Date(y, m - 1, d + days);
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}-${String(next.getDate()).padStart(2, '0')}`;
}

function todayIso() {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
}

function buildChartData(summary, minDays = 10) {
  const byDate = new Map();
  for (const r of summary) {
    if (r.date) byDate.set(r.date, r.total_pnl || 0);
  }
  const keys = [...byDate.keys()].sort();
  const endIso = keys.length ? keys[keys.length - 1] : todayIso();
  let startIso = addDaysIso(endIso, -(minDays - 1));
  if (keys.length && keys[0] < startIso) startIso = keys[0];

  const rows = [];
  for (let cur = startIso; cur <= endIso; cur = addDaysIso(cur, 1)) {
    rows.push({ date: cur, label: formatDate(cur), pnl: Math.round((byDate.get(cur) ?? 0) * 100) / 100 });
  }
  return rows;
}

export default function SimTrades() {
  const [trades, setTrades] = useState([]);
  const [summary, setSummary] = useState([]);
  const [dateFilter, setDateFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [settling, setSettling] = useState(false);
  const [settleMsg, setSettleMsg] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [t, s] = await Promise.all([
        getSimTrades(dateFilter || null),
        getSimSummary(),
      ]);
      setTrades(t.data);
      setSummary(s.data);
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to load simulated trades');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [dateFilter]);

  const handleSettle = async () => {
    setSettling(true);
    setSettleMsg('');
    setError('');
    try {
      const { data } = await settleSimTrades();
      setSettleMsg(data.message || `Settled ${data.settled} trade(s)`);
      await load();
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to settle trades');
    } finally {
      setSettling(false);
    }
  };

  const chartData = useMemo(() => buildChartData(summary), [summary]);

  const totalPnl = summary.reduce((s, r) => s + (r.total_pnl || 0), 0);
  const totalTrades = summary.reduce((s, r) => s + (r.trades || 0), 0);
  const winDays = summary.filter(r => (r.total_pnl || 0) > 0).length;
  const winRate = summary.length ? Math.round((winDays / summary.length) * 100) : 0;
  const openCount = trades.filter(t => t.status === 'open').length;

  const yMax = Math.max(...chartData.map(d => Math.abs(d.pnl)), 50);
  const yDomain = [-yMax * 1.2, yMax * 1.2];

  return (
    <div className="sim-page">
      <div className="sim-page-header">
        <h1 className="page-title">Paper trading</h1>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={handleSettle}
          disabled={settling || loading}
        >
          {settling ? 'Settling…' : '⟳ Settle open trades'}
        </button>
      </div>

      {error && <div className="alert-error">{error}</div>}
      {settleMsg && !error && <div className="alert-info">{settleMsg}</div>}

      <div className="sim-stats-grid">
        <div className="stat-tile">
          <span className="stat-label">Total sim P&L</span>
          <span className={`stat-value ${totalPnl >= 0 ? 'positive' : 'negative'}`}>
            ₹{totalPnl.toFixed(2)}
          </span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Total trades</span>
          <span className="stat-value">{totalTrades}</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Win rate (days)</span>
          <span className="stat-value">{winRate}%</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Open (unsettled)</span>
          <span className={`stat-value ${openCount > 0 ? 'warn' : ''}`}>{openCount}</span>
        </div>
      </div>

      <div className="card chart-card">
        <div className="section-title">Daily sim P&L</div>
        <div className="pnl-chart-wrap">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }} barCategoryGap="25%">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="label" stroke="var(--text-muted)" tick={{ fontSize: 11 }} interval={0} />
              <YAxis
                stroke="var(--text-muted)"
                tick={{ fontSize: 11 }}
                tickFormatter={v => `₹${Math.round(v)}`}
                domain={yDomain}
                width={56}
              />
              <ReferenceLine y={0} stroke="var(--border)" strokeDasharray="4 4" />
              <Tooltip
                contentStyle={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8 }}
                labelFormatter={(_, items) => items?.[0]?.payload?.date ?? ''}
                formatter={v => [`₹${Number(v).toFixed(2)}`, 'Sim P&L']}
              />
              <Bar dataKey="pnl" radius={[4, 4, 0, 0]} maxBarSize={40} minPointSize={3}>
                {chartData.map((d, i) => (
                  <Cell key={`${d.date}-${i}`} fill={barColor(d.pnl)} fillOpacity={d.pnl === 0 ? 0.25 : 1} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card pnl-symbol-card">
        <div className="pnl-table-header">
          <div>
            <span className="section-title">Simulated trades</span>
            <span className="sim-badge">SIM</span>
          </div>
          <input type="date" value={dateFilter} onChange={e => setDateFilter(e.target.value)} />
        </div>

        {loading ? (
          <div className="empty-state">Loading…</div>
        ) : trades.length === 0 ? (
          <div className="empty-state">
            No simulated trades{dateFilter ? ` for ${dateFilter}` : ''}. Enable paper mode and start the bot.
          </div>
        ) : (
          <div className="pnl-symbol-scroll">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Qty</th>
                  <th>Entry</th>
                  <th>SL</th>
                  <th>Target</th>
                  <th>Exit</th>
                  <th>P&L</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {trades.map(t => (
                  <tr key={t.id}>
                    <td className="muted">{t.executed_at?.slice(0, 10)}</td>
                    <td><strong>{t.symbol}</strong></td>
                    <td className={t.side === 'BUY' ? 'positive' : 'negative'}>{t.side}</td>
                    <td>{t.quantity}</td>
                    <td>₹{parseFloat(t.entry_price).toFixed(2)}</td>
                    <td className="negative">₹{parseFloat(t.stop_loss).toFixed(2)}</td>
                    <td className="positive">₹{parseFloat(t.target).toFixed(2)}</td>
                    <td>{t.exit_price != null ? `₹${parseFloat(t.exit_price).toFixed(2)}` : '—'}</td>
                    <td className={t.pnl == null ? 'muted' : parseFloat(t.pnl) >= 0 ? 'positive' : 'negative'}>
                      {t.pnl != null ? `₹${parseFloat(t.pnl).toFixed(2)}` : '—'}
                    </td>
                    <td>
                      <span className={`sim-status sim-status-${t.status}`}>{t.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
