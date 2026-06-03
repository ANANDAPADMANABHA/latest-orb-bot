import { useState, useEffect, useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ReferenceLine
} from 'recharts';
import { getPnLHistory, getPnLSummary, syncPnL } from '../api/client';
import './PnL.css';

const MIN_CHART_DAYS = 10;

function normalizeDateKey(value) {
  if (!value) return '';
  return String(value).slice(0, 10);
}

function formatIsoDate(y, m, d) {
  return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

function todayIsoLocal() {
  const now = new Date();
  return formatIsoDate(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

function addDaysIso(iso, days) {
  const [y, m, d] = iso.split('-').map(Number);
  const next = new Date(y, m - 1, d + days);
  return formatIsoDate(next.getFullYear(), next.getMonth() + 1, next.getDate());
}

function formatChartDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
}

function aggregateDailyPnL(summary, records) {
  const byDate = new Map();

  for (const row of summary) {
    const key = normalizeDateKey(row.date);
    if (!key) continue;
    byDate.set(key, Number(row.total_pnl) || 0);
  }

  if (byDate.size === 0) {
    for (const row of records) {
      const key = normalizeDateKey(row.date);
      if (!key) continue;
      byDate.set(key, (byDate.get(key) || 0) + (Number(row.pnl) || 0));
    }
  }

  return byDate;
}

/** Ensure at least MIN_CHART_DAYS on the x-axis; fill missing days with zero P&L. */
function buildPaddedChartData(summary, records, minDays = MIN_CHART_DAYS) {
  const byDate = aggregateDailyPnL(summary, records);
  const datedKeys = [...byDate.keys()].sort();

  let endIso = todayIsoLocal();
  if (datedKeys.length && datedKeys[datedKeys.length - 1] > endIso) {
    endIso = datedKeys[datedKeys.length - 1];
  }

  let startIso = addDaysIso(endIso, -(minDays - 1));
  if (datedKeys.length && datedKeys[0] < startIso) {
    startIso = datedKeys[0];
  }

  const rows = [];
  for (let cur = startIso; cur <= endIso; cur = addDaysIso(cur, 1)) {
    const pnl = byDate.get(cur) ?? 0;
    rows.push({
      date: cur,
      label: formatChartDate(cur),
      pnl: Math.round(pnl * 100) / 100,
    });
  }

  return rows;
}

function barColor(pnl) {
  if (pnl > 0) return 'var(--green)';
  if (pnl < 0) return 'var(--red)';
  return 'var(--text-muted)';
}

function formatPnlPercent(pct) {
  if (pct === null || pct === undefined || !Number.isFinite(Number(pct))) return '—';
  const n = Number(pct);
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function chartYDomain(data) {
  const values = data.map(d => d.pnl);
  const maxPnl = Math.max(...values, 0);
  const minPnl = Math.min(...values, 0);

  if (maxPnl === 0 && minPnl === 0) {
    return [-100, 100];
  }

  const span = Math.max(maxPnl - minPnl, 50);
  const pad = span * 0.2;
  return [minPnl - pad, maxPnl + pad];
}

export default function PnL() {
  const [records, setRecords] = useState([]);
  const [summary, setSummary] = useState([]);
  const [dateFilter, setDateFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  const [error, setError] = useState('');

  const load = async ({ syncFirst = false } = {}) => {
    setLoading(true);
    setError('');
    if (syncFirst) {
      setSyncing(true);
      setSyncMessage('');
    }
    try {
      if (syncFirst) {
        try {
          const { data } = await syncPnL();
          setSyncMessage(data.message || `Synced ${data.synced} record(s)`);
        } catch (e) {
          setError(e.response?.data?.error || 'Failed to sync P&L from broker');
        }
      }
      const [r, s] = await Promise.all([
        getPnLHistory(dateFilter || null),
        getPnLSummary(),
      ]);
      setRecords(r.data);
      setSummary(s.data);
    } catch (e) {
      if (!syncFirst || !error) {
        setError(e.response?.data?.error || 'Failed to load P&L data');
      }
    } finally {
      setLoading(false);
      if (syncFirst) setSyncing(false);
    }
  };

  const handleSync = async () => {
    await load({ syncFirst: true });
  };

  useEffect(() => {
    load({ syncFirst: !dateFilter });
  }, [dateFilter]);

  const totalFiltered = records.reduce((s, r) => s + parseFloat(r.pnl || 0), 0);
  const chartData = useMemo(
    () => buildPaddedChartData(summary, records),
    [summary, records],
  );
  const yDomain = useMemo(() => chartYDomain(chartData), [chartData]);
  const hasTradeData = summary.length > 0;

  return (
    <div className="pnl-page">
      <div className="pnl-page-header">
        <h1 className="page-title">P&L History</h1>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={handleSync}
          disabled={syncing || loading}
        >
          {syncing ? 'Syncing…' : '⟳ Sync from broker'}
        </button>
      </div>

      {error && <div className="alert-error">{error}</div>}
      {syncMessage && !error && <div className="alert-info">{syncMessage}</div>}

      <div className="card chart-card">
        <div className="section-title">Daily P&L Chart</div>
        {!hasTradeData && (
          <div className="chart-hint">
            No trades synced yet — chart shows the last {MIN_CHART_DAYS} days.
          </div>
        )}
        <div className="pnl-chart-wrap">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart
              data={chartData}
              margin={{ top: 8, right: 12, left: 4, bottom: 4 }}
              barCategoryGap="25%"
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="label"
                stroke="var(--text-muted)"
                tick={{ fontSize: 11 }}
                interval={0}
              />
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
                formatter={v => [`₹${Number(v).toFixed(2)}`, 'P&L']}
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

      <div className="card">
        <div className="pnl-table-header">
          <div>
            <span className="section-title">P&L by symbol</span>
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
          <div className="empty-state">
            No records{dateFilter ? ` for ${dateFilter}` : ''}. Sync from broker after trading.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Symbol</th>
                <th>Qty</th>
                <th>P&L</th>
                <th>P&L %</th>
              </tr>
            </thead>
            <tbody>
              {records.map(r => {
                const pct = r.pnl_percent;
                return (
                <tr key={r.id}>
                  <td className="muted">{r.date}</td>
                  <td><strong>{r.symbol}</strong></td>
                  <td>{r.quantity}</td>
                  <td className={parseFloat(r.pnl) >= 0 ? 'positive' : 'negative'}>
                    ₹{parseFloat(r.pnl).toFixed(2)}
                  </td>
                  <td
                    className={
                      pct === null || pct === undefined
                        ? 'muted'
                        : pct >= 0
                          ? 'positive'
                          : 'negative'
                    }
                    title={
                      r.invested_capital
                        ? `P&L ÷ invested capital (₹${parseFloat(r.invested_capital).toFixed(2)})`
                        : 'Re-sync from broker to refresh invested capital'
                    }
                  >
                    {formatPnlPercent(pct)}
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
