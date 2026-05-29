import { useState, useCallback, useEffect } from 'react';
import { Link } from 'react-router-dom';
import StockChart from '../components/StockChart';
import useChartLiveSocket from '../hooks/useChartLiveSocket';
import { getWatchlistCharts } from '../api/client';
import './Charts.css';

export default function Charts() {
  const [symbols, setSymbols] = useState([]);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const hasSymbols = symbols.length > 0;
  const { ticks: liveTicks, status: liveStatus, statusDetail } = useChartLiveSocket(true);

  const load = useCallback(async (forceRefresh = false) => {
    setLoading(true);
    setError('');
    try {
      const { data } = await getWatchlistCharts(forceRefresh);
      setSymbols(data.symbols || []);
      setUpdatedAt(data.updated_at || null);
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Failed to load charts';
      setError(msg);
      setSymbols((prev) => (forceRefresh ? prev : []));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  const formattedUpdated = updatedAt
    ? new Date(updatedAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
    : null;

  const liveLabel =
    liveStatus === 'live' ? 'Live' :
    liveStatus === 'connecting' ? 'Connecting…' :
    liveStatus === 'connected' ? 'Connected' :
    liveStatus === 'reconnecting' ? 'Reconnecting…' :
    liveStatus === 'error' ? 'Live error' :
    liveStatus === 'disconnected' ? 'Offline' :
    liveStatus === 'no_tokens' ? 'No tokens' :
    liveStatus === 'no_symbols' ? 'No symbols' : null;

  return (
    <div className="charts-page">
      <div className="charts-header">
        <div>
          <h1 className="page-title">Charts</h1>
          <p className="page-sub">
            Historical 5-minute candles load once; live price updates stream via Angel One WebSocket.
            Use Refresh to reload history (sparingly). Live prices need market hours and a green Live badge.
          </p>
        </div>
        <div className="charts-header-actions">
          {liveLabel && (
            <span
              className={`charts-live-badge charts-live-${liveStatus}`}
              title={statusDetail || undefined}
            >
              {liveLabel}
            </span>
          )}
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => load(true)}
            disabled={loading}
          >
            {loading ? 'Loading…' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && <div className="charts-error">{error}</div>}

      {formattedUpdated && !error && (
        <p className="charts-updated">History loaded: {formattedUpdated}</p>
      )}

      {loading && symbols.length === 0 && !error && (
        <div className="empty-state">Loading chart data…</div>
      )}

      {!loading && symbols.length === 0 && !error && (
        <div className="card charts-empty">
          <p className="empty-state">
            No symbols on your watchlist.{' '}
            <Link to="/watchlist">Add tickers on Watchlist</Link> then refresh.
          </p>
        </div>
      )}

      {symbols.length > 0 && (
        <>
          <div className="charts-grid">
            {symbols.map((s) => (
              <StockChart
                key={s.symbol}
                symbol={s.symbol}
                candles={s.candles}
                orbHigh={s.orb_high}
                orbLow={s.orb_low}
                lastClose={s.last_close}
                error={s.error}
                liveTick={liveTicks[s.symbol]}
              />
            ))}
          </div>
          <p className="charts-attribution">
            Charts powered by{' '}
            <a
              href="https://www.tradingview.com/"
              target="_blank"
              rel="noopener noreferrer"
            >
              TradingView
            </a>{' '}
            Lightweight Charts · Live data via{' '}
            <a
              href="https://smartapi.angelbroking.com/docs/WebSocket2"
              target="_blank"
              rel="noopener noreferrer"
            >
              Angel One SmartAPI WebSocket v2
            </a>
          </p>
        </>
      )}
    </div>
  );
}
