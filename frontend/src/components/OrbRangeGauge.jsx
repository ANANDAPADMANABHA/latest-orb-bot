import './OrbRangeGauge.css';

function formatPrice(v) {
  if (v == null || Number.isNaN(Number(v))) return '—';
  return `₹${Number(v).toFixed(2)}`;
}

export default function OrbRangeGauge({ symbol, orbHigh, orbLow, lastClose, error }) {
  const hasOrb = orbHigh != null && orbLow != null;
  const low = Number(orbLow);
  const high = Number(orbHigh);
  const price = Number(lastClose);

  let positionPct = 50;
  if (hasOrb && high > low && !Number.isNaN(price)) {
    positionPct = ((price - low) / (high - low)) * 100;
    positionPct = Math.max(0, Math.min(100, positionPct));
  }

  const aboveRange = hasOrb && !Number.isNaN(price) && price > high;
  const belowRange = hasOrb && !Number.isNaN(price) && price < low;

  if (error && !hasOrb) {
    return (
      <div className="orb-gauge card">
        <div className="orb-gauge-symbol">{symbol}</div>
        <div className="orb-gauge-empty">{error}</div>
      </div>
    );
  }

  if (!hasOrb) {
    return (
      <div className="orb-gauge card">
        <div className="orb-gauge-symbol">{symbol}</div>
        <div className="orb-gauge-empty">ORB levels unavailable</div>
      </div>
    );
  }

  return (
    <div className="orb-gauge card">
      <div className="orb-gauge-header">
        <span className="orb-gauge-symbol">{symbol}</span>
        <span className="orb-gauge-now">{formatPrice(lastClose)}</span>
      </div>

      <div className="orb-gauge-visual" aria-label={`${symbol} opening range`}>
        <div className="orb-gauge-scale">
          <span className="orb-label orb-label-high">{formatPrice(high)}</span>
          <span className="orb-label orb-label-low">{formatPrice(low)}</span>
        </div>

        <div className="orb-gauge-track">
          <span className="orb-dot orb-dot-end orb-dot-high" title="ORB High" />
          <div className="orb-gauge-line">
            <div
              className="orb-dot orb-dot-price"
              style={{ left: `${positionPct}%` }}
              title="Current price"
            />
          </div>
          <span className="orb-dot orb-dot-end orb-dot-low" title="ORB Low" />
        </div>

        <div className="orb-gauge-legend">
          <span className="legend-high">ORB High</span>
          <span className={`legend-now${aboveRange ? ' breakout-up' : ''}${belowRange ? ' breakout-down' : ''}`}>
            {aboveRange ? 'Above range' : belowRange ? 'Below range' : 'In range'}
          </span>
          <span className="legend-low">ORB Low</span>
        </div>
      </div>
    </div>
  );
}
