import { useState, useEffect } from 'react';
import { getBotStatus, startBot, stopBot } from '../api/client';
import './BotControl.css';

export default function BotControl() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchStatus = async () => {
    try {
      const { data } = await getBotStatus();
      setStatus(data);
    } catch {
      setError('Failed to fetch bot status');
    }
  };

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 10000);
    return () => clearInterval(id);
  }, []);

  const handleStart = async () => {
    setLoading(true);
    setError('');
    try {
      await startBot();
      await fetchStatus();
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to start bot');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    setError('');
    try {
      await stopBot();
      await fetchStatus();
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to stop bot');
    } finally {
      setLoading(false);
    }
  };

  const isRunning = status?.is_running;

  return (
    <div className="bot-control card">
      <div className="bot-control-header">
        <div>
          <div className="bot-control-title">Bot Control</div>
          <div className="bot-control-sub">Weekday auto-run at 9:20 AM IST</div>
        </div>
        <div className={`bot-indicator ${isRunning ? 'on' : 'off'}`}>
          <span className="dot" />
          {isRunning ? 'Running' : 'Stopped'}
        </div>
      </div>

      {error && <div className="bot-error">{error}</div>}

      <div className="bot-control-actions">
        <button
          className="btn btn-primary"
          onClick={handleStart}
          disabled={loading || isRunning}
        >
          {loading && !isRunning ? '...' : '▶ Start Bot'}
        </button>
        <button
          className="btn btn-danger"
          onClick={handleStop}
          disabled={loading || !isRunning}
        >
          {loading && isRunning ? '...' : '■ Stop Bot'}
        </button>
      </div>

      {status?.session && (
        <div className="bot-session-info">
          <span>Session #{status.session.id}</span>
          <span>Started: {new Date(status.session.started_at).toLocaleTimeString('en-IN')}</span>
          <span className={`badge badge-${
            status.session.status === 'running' ? 'green' :
            status.session.status === 'completed' ? 'blue' :
            status.session.status === 'error' ? 'red' : 'gray'
          }`}>{status.session.status}</span>
        </div>
      )}
    </div>
  );
}
