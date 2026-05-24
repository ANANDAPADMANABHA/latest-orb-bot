import { useState, useEffect } from 'react';
import { getPositions, getOrders } from '../api/client';
import './Positions.css';

export default function Positions() {
  const [positions, setPositions] = useState([]);
  const [orders, setOrders] = useState([]);
  const [posLoading, setPosLoading] = useState(true);
  const [ordLoading, setOrdLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = async () => {
    setPosLoading(true);
    setOrdLoading(true);
    try {
      const [p, o] = await Promise.all([getPositions(), getOrders()]);
      setPositions(p.data || []);
      setOrders(o.data || []);
    } catch (e) {
      setError(e.response?.data?.error || 'Could not connect to Angel One. Check your credentials.');
    } finally {
      setPosLoading(false);
      setOrdLoading(false);
    }
  };

  useEffect(() => { reload(); }, []);

  const totalPnl = positions.reduce((s, p) => s + parseFloat(p.pnl || 0), 0);

  return (
    <div className="positions-page">
      <div className="positions-header">
        <h1 className="page-title">Live Positions & Orders</h1>
        <button className="btn btn-ghost btn-sm" onClick={reload}>⟳ Refresh</button>
      </div>

      {error && <div className="alert-error">{error}</div>}

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
        ) : positions.length === 0 ? (
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
              </tr>
            </thead>
            <tbody>
              {positions.map((p, i) => (
                <tr key={i}>
                  <td><strong>{p.tradingsymbol}</strong></td>
                  <td>{p.netqty ?? p.quantity}</td>
                  <td>₹{parseFloat(p.buyavgprice || 0).toFixed(2)}</td>
                  <td>₹{parseFloat(p.sellavgprice || 0).toFixed(2)}</td>
                  <td className={parseFloat(p.pnl) >= 0 ? 'positive' : 'negative'}>
                    ₹{parseFloat(p.pnl || 0).toFixed(2)}
                  </td>
                  <td><span className="badge badge-blue">{p.producttype}</span></td>
                </tr>
              ))}
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
                      o.orderstatus === 'complete' ? 'badge-green' :
                      o.orderstatus === 'open'     ? 'badge-blue' :
                      o.orderstatus === 'rejected' ? 'badge-red' : 'badge-gray'
                    }`}>{o.orderstatus}</span>
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
