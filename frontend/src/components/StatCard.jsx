import './StatCard.css';

export default function StatCard({ label, value, sub, color }) {
  return (
    <div className="stat-card card">
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={color ? { color } : {}}>
        {value ?? '—'}
      </div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}
