import { useState, useEffect } from 'react';
import { getWatchlist, addTicker, deleteTicker, getChartinkWebhookConfig } from '../api/client';
import './Watchlist.css';

export default function Watchlist() {
  const [tickers, setTickers] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [webhookConfig, setWebhookConfig] = useState(null);
  const [copied, setCopied] = useState(false);

  const load = async () => {
    const { data } = await getWatchlist();
    setTickers(data);
  };

  const loadWebhookConfig = async () => {
    try {
      const { data } = await getChartinkWebhookConfig();
      setWebhookConfig(data);
    } catch {
      setWebhookConfig({ enabled: false });
    }
  };

  useEffect(() => {
    load();
    loadWebhookConfig();
  }, []);

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

  const handleCopyWebhook = async () => {
    if (!webhookConfig?.webhook_url) return;
    try {
      await navigator.clipboard.writeText(webhookConfig.webhook_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError('Could not copy — select and copy the URL manually');
    }
  };

  return (
    <div className="watchlist-page">
      <h1 className="page-title">Watchlist</h1>
      <p className="page-sub">
        Tickers the ORB bot scans each trading day. Use manual add below, or let Chartink
        replace the list automatically at 11:00 AM IST via webhook.
      </p>

      {webhookConfig?.enabled && webhookConfig.webhook_url && (
        <div className="card chartink-card">
          <div className="chartink-title">Chartink webhook</div>
          <p className="chartink-hint">
            Paste this URL into your Chartink scanner alert (Create/Modify Alert → Webhook URL).
            Schedule the alert for <strong>weekdays 11:00 AM IST</strong>. Each alert replaces
            the watchlist and starts the bot.
          </p>
          <div className="chartink-url-row">
            <code className="chartink-url">{webhookConfig.webhook_url}</code>
            <button type="button" className="btn btn-ghost btn-sm" onClick={handleCopyWebhook}>
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          {webhookConfig.instructions && (
            <p className="chartink-note muted">{webhookConfig.instructions}</p>
          )}
        </div>
      )}

      {webhookConfig && !webhookConfig.enabled && (
        <div className="card chartink-card chartink-disabled">
          <div className="chartink-title">Chartink webhook</div>
          <p className="chartink-hint muted">
            Not configured. Set <code>CHARTINK_WEBHOOK_SECRET</code> in server <code>.env</code> and redeploy.
          </p>
        </div>
      )}

      <div className="card">
        <form className="add-ticker-form" onSubmit={handleAdd}>
          <input
            value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            placeholder="Add symbol manually (e.g. TCS)"
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
          <div className="empty-state">No tickers in watchlist. Add manually or wait for Chartink at 11 AM.</div>
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
