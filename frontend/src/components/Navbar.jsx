import { NavLink } from 'react-router-dom';
import './Navbar.css';

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/watchlist', label: 'Watchlist' },
  { to: '/charts', label: 'Charts' },
  { to: '/positions', label: 'Positions' },
  { to: '/pnl', label: 'P&L' },
  { to: '/sessions', label: 'Sessions' },
];

export default function Navbar() {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <span className="navbar-logo">📈</span>
        <span className="navbar-title">TradeMaster</span>
        <span className="navbar-sub">ORB Bot</span>
      </div>
      <ul className="navbar-links">
        {links.map(({ to, label }) => (
          <li key={to}>
            <NavLink to={to} end className={({ isActive }) => isActive ? 'active' : ''}>
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
