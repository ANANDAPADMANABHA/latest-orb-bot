import { useState, useEffect } from 'react';
import { getWatchlist, addTicker, deleteTicker } from '../api/client';
import './Watchlist.css';

export default function Watchlist() {
  const [tickers, setTickers] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    const { data } = await getWatchlist();
    setTickers(data);
  };

  useEffect(() => { load(); }, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    const symbol = input.trim().toUpperCase();
    if (!symbol) return;
    setLoading(true);
    setError('');
    try {
      await addTicker(symbol);
      setInput('');
      await load();
    } catch (err) {
      setError(err.response?.data?.symbol?.[0] || err.response?.data?.error || 'Failed to add ticker');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await deleteTicker(id);
      setTickers(prev => prev.filter(t => t.id !== id));
    } catch {
      setError('Failed to remove ticker');
    }
  };

  return (
    <div className="watchlist-page">
      <h1 className="page-title">Watchlist</h1>
      <p className="page-sub">
        Tickers the ORB bot will scan each trading day. Symbols must be valid NSE EQ names (e.g. <code>RELIANCE</code>, <code>INFY</code>).
      </p>

      <div className="card">
        <form className="add-ticker-form" onSubmit={handleAdd}>
          <input
            value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            placeholder="Add symbol (e.g. TCS)"
            maxLength={20}
          />
          <button className="btn btn-primary" type="submit" disabled={loading || !input.trim()}>
            {loading ? 'Adding…' : '+ Add'}
          </button>
        </form>
        {error && <div className="form-error">{error}</div>}
      </div>

      <div className="card">
        {tickers.length === 0 ? (
          <div className="empty-state">No tickers in watchlist. Add some above.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Symbol</th>
                <th>Added</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {tickers.map((t, i) => (
                <tr key={t.id}>
                  <td className="muted">{i + 1}</td>
                  <td><strong className="symbol">{t.symbol}</strong></td>
                  <td className="muted">{new Date(t.added_at).toLocaleDateString('en-IN')}</td>
                  <td>
                    <button
                      className="btn btn-ghost btn-sm remove-btn"
                      onClick={() => handleDelete(t.id)}
                    >
                      Remove
                    </button>
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
