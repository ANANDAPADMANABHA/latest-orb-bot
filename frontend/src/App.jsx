import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Watchlist from './pages/Watchlist';
import Positions from './pages/Positions';
import PnL from './pages/PnL';
import Sessions from './pages/Sessions';
import './App.css';

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Navbar />
        <main className="app-main">
          <Routes>
            <Route path="/"          element={<Dashboard />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/positions" element={<Positions />} />
            <Route path="/pnl"       element={<PnL />} />
            <Route path="/sessions"  element={<Sessions />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
