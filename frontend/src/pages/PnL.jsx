import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import { getPnLHistory, getPnLSummary } from '../api/client';
import './PnL.css';

export default function PnL() {
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState([]);
  const [dateFilter, setDateFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [r, s] = await Promise.all([
        getPnLHistory(dateFilter || null),
        getPnLSummary(),
      ]);
      setRecords(r.data);
      setSummary(s.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [dateFilter]);

  const totalFiltered = records.reduce((s, r) => s + parseFloat(r.pnl || 0), 0);
  const chartData = summary.map(d => ({
    date: d.date,
    pnl: parseFloat(d.total_pnl.toFixed(2)),
  }));

  return (
    <div className="pnl-page">
      <h1 className="page-title">P&L History</h1>

      <div className="card chart-card">
        <div className="section-title">Daily P&L Chart</div>
        {chartData.length === 0 ? (
          <div className="empty-state">No data yet</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" stroke="var(--text-muted)" tick={{ fontSize: 11 }} />
              <YAxis stroke="var(--text-muted)" tick={{ fontSize: 11 }} tickFormatter={v => `₹${v}`} />
              <Tooltip
                contentStyle={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 8 }}
                formatter={v => [`₹${v}`, 'P&L']}
              />
              <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                {chartData.map((d, i) => (
                  <Cell key={i} fill={d.pnl >= 0 ? 'var(--green)' : 'var(--red)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <div className="pnl-table-header">
          <div>
            <span className="section-title">Trade Records</span>
            {!loading && (
              <span className={`pnl-total ${totalFiltered >= 0 ? 'positive' : 'negative'}`}>
                {' '}— ₹{totalFiltered.toFixed(2)} total
              </span>
            )}
          </div>
          <input
            type="date"
            value={dateFilter}
            onChange={e => setDateFilter(e.target.value)}
          />
        </div>

        {loading ? (
          <div className="empty-state">Loading…</div>
        ) : records.length === 0 ? (
          <div className="empty-state">No records{dateFilter ? ` for ${dateFilter}` : ''}</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Symbol</th>
                <th>Qty</th>
                <th>P&L</th>
              </tr>
            </thead>
            <tbody>
              {records.map(r => (
                <tr key={r.id}>
                  <td className="muted">{r.date}</td>
                  <td><strong>{r.symbol}</strong></td>
                  <td>{r.quantity}</td>
                  <td className={parseFloat(r.pnl) >= 0 ? 'positive' : 'negative'}>
                    ₹{parseFloat(r.pnl).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
