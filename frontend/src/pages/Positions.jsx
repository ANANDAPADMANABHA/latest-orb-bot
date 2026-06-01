import { useState, useEffect } from 'react';
import { getBrokerLive, exitPosition, cleanupOrphanOrders } from '../api/client';
import './Positions.css';

function positionQty(p) {
  const net = p.netqty ?? p.netQty;
  if (net !== undefined && net !== null && net !== '') {
    const n = parseInt(Number(net), 10);
    if (!Number.isNaN(n)) return n;
  }
  const buy = parseInt(Number(p.buyqty ?? p.buyQty ?? 0), 10);
  const sell = parseInt(Number(p.sellqty ?? p.sellQty ?? 0), 10);
  return buy - sell;
}

export default function Positions() {
  const [positions, setPositions] = useState([]);
  const [orders, setOrders] = useState([]);
  const [posLoading, setPosLoading] = useState(true);
  const [ordLoading, setOrdLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [exitingSymbol, setExitingSymbol] = useState(null);
  const [cleaningOrphans, setCleaningOrphans] = useState(false);

  const reload = async () => {
    setPosLoading(true);
    setOrdLoading(true);
    setError('');
    try {
      const { data } = await getBrokerLive();
      setPositions(data.positions || []);
      setOrders(data.orders || []);
    } catch (e) {
      setError(
        e.response?.data?.error ||
          'Could not connect to Angel One. Wait 10–15 min if rate limited, then refresh once.'
      );
    } finally {
      setPosLoading(false);
      setOrdLoading(false);
    }
  };

  useEffect(() => { reload(); }, []);

  const handleExit = async (p) => {
    const symbol = p.tradingsymbol;
    const qty = positionQty(p);
    if (!symbol || qty === 0) return;

    const ok = window.confirm(
      `Exit ${symbol} at market (${qty} shares) and cancel pending orders?`
    );
    if (!ok) return;

    setExitingSymbol(symbol);
    setError('');
    setSuccess('');
    try {
      const { data } = await exitPosition(symbol);
      const cancelled = data.cancelled_orders?.length ?? 0;
      const placed = data.square_off?.placed;
      setSuccess(
        placed
          ? `Exit submitted for ${symbol}. Cancelled ${cancelled} pending order(s).`
          : `Orders cancelled for ${symbol}, but square-off failed: ${data.square_off?.error || 'unknown'}`
      );
      await reload();
    } catch (e) {
      setError(e.response?.data?.error || e.message || 'Failed to exit position');
    } finally {
      setExitingSymbol(null);
    }
  };

  const handleCleanupOrphans = async (symbolList) => {
    setCleaningOrphans(true);
    setError('');
    setSuccess('');
    try {
      const { data } = await cleanupOrphanOrders(symbolList);
      const n = data.cancelled_order_ids?.length ?? 0;
      const pending = data.pending_found?.length ?? 0;
      const book = data.order_book_count ?? 0;
      if (n > 0) {
        setSuccess(`Cancelled ${n} stale order(s): ${data.cancelled_order_ids.join(', ')}`);
      } else if (pending > 0 && data.errors?.length) {
        setError(
          `Found ${pending} pending order(s) but cancel failed. ${JSON.stringify(data.errors)}`
        );
      } else if (pending === 0 && book === 0) {
        setError('Angel One returned an empty order book. Wait if rate-limited, then refresh.');
      } else if (pending > 0) {
        setError(
          `Found ${pending} pending order(s) but none were cancelled. ` +
          'Position may still show as open at broker, or deploy latest backend.'
        );
      } else {
        setSuccess('No pending orders found in the order book.');
      }
      await reload();
    } catch (e) {
      setError(e.response?.data?.error || e.message || 'Cleanup failed');
    } finally {
      setCleaningOrphans(false);
    }
  };

  const totalPnl = positions.reduce((s, p) => s + parseFloat(p.pnl || 0), 0);
  const openPositions = positions.filter((p) => positionQty(p) !== 0);

  return (
    <div className="positions-page">
      <div className="positions-header">
        <h1 className="page-title">Live Positions & Orders</h1>
        <div className="positions-header-actions">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => handleCleanupOrphans()}
            disabled={cleaningOrphans}
          >
            {cleaningOrphans ? 'Cancelling…' : 'Cancel stale orders'}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={reload}>
            ⟳ Refresh
          </button>
        </div>
      </div>

      {error && <div className="alert-error">{error}</div>}
      {success && <div className="alert-success">{success}</div>}

      <div className="card">
        <div className="section-header">
          <span className="section-title">Positions</span>
          {!posLoading && positions.length > 0 && (
            <span className={`pnl-total ${totalPnl >= 0 ? 'positive' : 'negative'}`}>
              Total P&L: ₹{totalPnl.toFixed(2)}
            </span>
          )}
        </div>

        {posLoading ? (
          <div className="loading">Loading…</div>
        ) : openPositions.length === 0 ? (
          <div className="empty-state">No open positions</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Qty</th>
                <th>Buy Price</th>
                <th>Sell Price</th>
                <th>P&L</th>
                <th>Product</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {openPositions.map((p, i) => {
                const qty = positionQty(p);
                const canExit = qty !== 0;
                return (
                  <tr key={p.tradingsymbol || i}>
                    <td><strong>{p.tradingsymbol}</strong></td>
                    <td>{qty}</td>
                    <td>₹{parseFloat(p.buyavgprice || 0).toFixed(2)}</td>
                    <td>₹{parseFloat(p.sellavgprice || 0).toFixed(2)}</td>
                    <td className={parseFloat(p.pnl) >= 0 ? 'positive' : 'negative'}>
                      ₹{parseFloat(p.pnl || 0).toFixed(2)}
                    </td>
                    <td><span className="badge badge-blue">{p.producttype}</span></td>
                    <td className="positions-actions">
                      {canExit ? (
                        <button
                          type="button"
                          className="btn btn-danger btn-sm"
                          disabled={exitingSymbol === p.tradingsymbol}
                          onClick={() => handleExit(p)}
                        >
                          {exitingSymbol === p.tradingsymbol ? 'Exiting…' : 'Exit'}
                        </button>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div className="section-title">Order Book</div>
        {ordLoading ? (
          <div className="loading">Loading…</div>
        ) : orders.length === 0 ? (
          <div className="empty-state">No orders</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Type</th>
                <th>Qty</th>
                <th>Price</th>
                <th>Status</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o, i) => (
                <tr key={i}>
                  <td><strong>{o.tradingsymbol}</strong></td>
                  <td>
                    <span className={`badge ${o.transactiontype === 'BUY' ? 'badge-green' : 'badge-red'}`}>
                      {o.transactiontype}
                    </span>
                  </td>
                  <td>{o.quantity}</td>
                  <td>₹{parseFloat(o.price || 0).toFixed(2)}</td>
                  <td>
                    <span className={`badge ${
                      (o.orderstatus || o.status) === 'complete' ? 'badge-green' :
                      (o.orderstatus || o.status) === 'open'     ? 'badge-blue' :
                      (o.orderstatus || o.status) === 'rejected' ? 'badge-red' : 'badge-gray'
                    }`}>{o.orderstatus || o.status}</span>
                  </td>
                  <td className="muted">{o.updatetime || o.ordertime || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
