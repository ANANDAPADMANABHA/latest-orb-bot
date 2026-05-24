import { useState, useEffect } from 'react';
import { getSessions } from '../api/client';
import './Sessions.css';

const STATUS_BADGE = {
  running:   'badge-green',
  completed: 'badge-blue',
  stopped:   'badge-gray',
  error:     'badge-red',
};

export default function Sessions() {
  const [sessions, setSessions] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSessions()
      .then(r => setSessions(r.data))
      .finally(() => setLoading(false));
  }, []);

  const fmt = (iso) => iso ? new Date(iso).toLocaleString('en-IN') : '—';

  return (
    <div className="sessions-page">
      <h1 className="page-title">Bot Sessions</h1>

      <div className="card">
        {loading ? (
          <div className="empty-state">Loading…</div>
        ) : sessions.length === 0 ? (
          <div className="empty-state">No sessions recorded yet.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Started</th>
                <th>Ended</th>
                <th>Status</th>
                <th>Trades</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => (
                <>
                  <tr key={s.id}>
                    <td className="muted">#{s.id}</td>
                    <td>{fmt(s.started_at)}</td>
                    <td className="muted">{fmt(s.stopped_at)}</td>
                    <td>
                      <span className={`badge ${STATUS_BADGE[s.status] || 'badge-gray'}`}>
                        {s.status}
                      </span>
                    </td>
                    <td>{s.trades?.length ?? 0}</td>
                    <td>
                      {(s.log || s.trades?.length > 0) && (
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                        >
                          {expanded === s.id ? 'Hide' : 'Details'}
                        </button>
                      )}
                    </td>
                  </tr>
                  {expanded === s.id && (
                    <tr key={`${s.id}-detail`} className="detail-row">
                      <td colSpan={6}>
                        {s.log && (
                          <div className="session-log">
                            <strong>Error log:</strong>
                            <pre>{s.log}</pre>
                          </div>
                        )}
                        {s.trades?.length > 0 && (
                          <table className="inner-table">
                            <thead>
                              <tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>SL</th><th>Target</th></tr>
                            </thead>
                            <tbody>
                              {s.trades.map(t => (
                                <tr key={t.id}>
                                  <td>{t.symbol}</td>
                                  <td>
                                    <span className={`badge ${t.side === 'BUY' ? 'badge-green' : 'badge-red'}`}>
                                      {t.side}
                                    </span>
                                  </td>
                                  <td>{t.quantity}</td>
                                  <td>₹{t.entry_price}</td>
                                  <td className="negative">₹{t.stop_loss}</td>
                                  <td className="positive">₹{t.target}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
