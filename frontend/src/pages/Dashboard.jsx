import { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import StatCard from '../components/StatCard';
import BotControl from '../components/BotControl';
import SystemStatus from '../components/SystemStatus';
import { getCapital, getPnLToday, getPnLSummary } from '../api/client';
import './Dashboard.css';

export default function Dashboard() {
  const [capital, setCapital] = useState(null);
  const [today, setToday] = useState(null);
  const [summary, setSummary] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const [healthProbeTrigger, setHealthProbeTrigger] = useState(0);

  const loadDashboard = useCallback(async () => {
    setRefreshing(true);
    setHealthProbeTrigger((n) => n + 1);
    try {
      await Promise.all([
        getCapital().then(r => setCapital(r.data.capital)).catch(() => {}),
        getPnLToday().then(r => setToday(r.data)).catch(() => {}),
        getPnLSummary().then(r => setSummary(r.data)).catch(() => {}),
      ]);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const totalPnl = summary.reduce((s, d) => s + d.total_pnl, 0);
  const winDays = summary.filter(d => d.total_pnl > 0).length;

  const chartData = summary.map(d => ({
    date: d.date,
    pnl: parseFloat(d.total_pnl.toFixed(2)),
  }));

  return (
    <div className="dashboard">
      <div className="dashboard-top-row">
        <h1 className="page-title">Dashboard</h1>
        <button
          type="button"
          className="btn btn-primary"
          onClick={loadDashboard}
          disabled={refreshing}
        >
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className="stats-grid">
        <StatCard
          label="Available Capital"
          value={capital != null ? `₹${capital.toLocaleString('en-IN')}` : '—'}
          sub="from Angel One RMS"
        />
        <StatCard
          label="Today's P&L"
          value={today ? `₹${parseFloat(today.total_pnl).toFixed(2)}` : '—'}
          color={today?.total_pnl >= 0 ? 'var(--green)' : 'var(--red)'}
          sub={`${today?.trades?.length ?? 0} trade(s) today`}
        />
        <StatCard
          label="Total P&L"
          value={`₹${totalPnl.toFixed(2)}`}
          color={totalPnl >= 0 ? 'var(--green)' : 'var(--red)'}
          sub={`${summary.length} sessions tracked`}
        />
        <StatCard
          label="Win Days"
          value={`${winDays} / ${summary.length}`}
          sub={summary.length ? `${((winDays / summary.length) * 100).toFixed(0)}% win rate` : ''}
        />
      </div>

      <SystemStatus probeTrigger={healthProbeTrigger} />

      <BotControl />

      <div className="card chart-card">
        <div className="section-title">Daily P&L History</div>
        {chartData.length === 0 ? (
          <div className="empty-state">No P&L data yet</div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#4f8ef7" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#4f8ef7" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" stroke="var(--text-muted)" tick={{ fontSize: 11 }} />
              <YAxis stroke="var(--text-muted)" tick={{ fontSize: 11 }} tickFormatter={v => `₹${v}`} />
              <Tooltip
                contentStyle={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8 }}
                formatter={v => [`₹${v}`, 'P&L']}
              />
              <Area type="monotone" dataKey="pnl" stroke="#4f8ef7" fill="url(#pnlGrad)" strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {today?.trades?.length > 0 && (
        <div className="card">
          <div className="section-title">Today&apos;s Trades</div>
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Qty</th>
                <th>P&L</th>
              </tr>
            </thead>
            <tbody>
              {today.trades.map(t => (
                <tr key={t.id}>
                  <td><strong>{t.symbol}</strong></td>
                  <td>{t.quantity}</td>
                  <td className={parseFloat(t.pnl) >= 0 ? 'positive' : 'negative'}>
                    ₹{parseFloat(t.pnl).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
