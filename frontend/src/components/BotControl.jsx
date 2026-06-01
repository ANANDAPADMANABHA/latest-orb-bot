import { useState, useEffect } from 'react';
import { getBotStatus, startBot, stopBot, updateBotSettings } from '../api/client';
import './BotControl.css';

const STRATEGIES = [
  {
    id: 'fixed_percent',
    label: 'Fixed % (1% SL / 2% target)',
    description: 'Stop loss and target as fixed percentages of LTP.',
  },
  {
    id: 'prev_candle',
    label: 'Previous 5m candle (low/high SL, 1% target)',
    description: 'Long: SL at previous candle low. Short: SL at previous candle high. Target 1% from LTP.',
  },
  {
    id: 'trailing_candle',
    label: 'Trailing stop (prev candle SL, 5% target)',
    description: 'Long: initial SL at prev candle low; breakeven at +1%; trails candle lows after +2%. Target +5%. Short mirrored.',
  },
];

const RISK_OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

const CAPITAL_USAGE_OPTIONS = [
  {
    value: 100,
    label: '100% of available cash',
    description: 'Maximum shares = floor(capital ÷ price) for one position.',
  },
  {
    value: 50,
    label: '50% of available cash',
    description: 'Leave half your balance free for other trades or margin.',
  },
];

export default function BotControl() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [strategyLoading, setStrategyLoading] = useState(false);
  const [riskLoading, setRiskLoading] = useState(false);
  const [capitalUsageLoading, setCapitalUsageLoading] = useState(false);
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');

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
    const id = setInterval(fetchStatus, 5000);
    return () => clearInterval(id);
  }, []);

  const handleStart = async () => {
    setLoading(true);
    setError('');
    setWarning('');
    try {
      const { data } = await startBot();
      if (data.warning) {
        setWarning(data.warning);
      }
      await fetchStatus();
      // Poll quickly while Celery worker picks up the task
      for (let i = 0; i < 15; i += 1) {
        await new Promise((r) => setTimeout(r, 2000));
        await fetchStatus();
        const { data: st } = await getBotStatus();
        if (st?.is_running) break;
      }
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
      for (let i = 0; i < 6; i += 1) {
        await new Promise((r) => setTimeout(r, 2000));
        const { data: st } = await getBotStatus();
        if (!st?.is_running) break;
        await fetchStatus();
      }
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to stop bot');
    } finally {
      setLoading(false);
    }
  };

  const handleStrategyChange = async (strategyId) => {
    if (strategyLoading || status?.settings?.stop_loss_strategy === strategyId) {
      return;
    }
    setStrategyLoading(true);
    setError('');
    try {
      await updateBotSettings({ stop_loss_strategy: strategyId });
      await fetchStatus();
    } catch (e) {
      setError(e.response?.data?.stop_loss_strategy?.[0] || e.response?.data?.error || 'Failed to update strategy');
    } finally {
      setStrategyLoading(false);
    }
  };

  const handleRiskChange = async (percent) => {
    const next = Number(percent);
    if (riskLoading || status?.settings?.risk_percent === next) {
      return;
    }
    setRiskLoading(true);
    setError('');
    try {
      await updateBotSettings({ risk_percent: next });
      await fetchStatus();
    } catch (e) {
      setError(
        e.response?.data?.risk_percent?.[0]
        || e.response?.data?.error
        || 'Failed to update risk percent',
      );
    } finally {
      setRiskLoading(false);
    }
  };

  const handleCapitalUsageChange = async (percent) => {
    const next = Number(percent);
    if (capitalUsageLoading || status?.settings?.max_capital_usage_percent === next) {
      return;
    }
    setCapitalUsageLoading(true);
    setError('');
    try {
      await updateBotSettings({ max_capital_usage_percent: next });
      await fetchStatus();
    } catch (e) {
      setError(
        e.response?.data?.max_capital_usage_percent?.[0]
        || e.response?.data?.error
        || 'Failed to update capital usage',
      );
    } finally {
      setCapitalUsageLoading(false);
    }
  };

  const isRunning = Boolean(status?.is_running);
  const heartbeatStale = Boolean(status?.heartbeat_stale);
  const activeStrategy = status?.settings?.stop_loss_strategy || 'fixed_percent';
  const activeRisk = status?.settings?.risk_percent ?? 1;
  const activeCapitalUsage = status?.settings?.max_capital_usage_percent ?? 100;

  return (
    <div className="bot-control card">
      <div className="bot-control-header">
        <div>
          <div className="bot-control-title">Bot Control</div>
          <div className="bot-control-sub">Weekday auto-run at 9:20 AM IST</div>
        </div>
        <div className={`bot-indicator ${isRunning ? (heartbeatStale ? 'warn' : 'on') : 'off'}`}>
          <span className="dot" />
          {isRunning
            ? (heartbeatStale ? 'Running (stale)' : 'Running')
            : 'Stopped'}
        </div>
      </div>

      {error && <div className="bot-error">{error}</div>}
      {warning && <div className="bot-warning">{warning}</div>}

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

      <div className="bot-strategy-section">
        <div className="bot-strategy-title">Stop-loss strategy</div>
        <p className="bot-strategy-hint">Applies from the next trade.</p>
        <div className="bot-strategy-options">
          {STRATEGIES.map((s) => (
            <label key={s.id} className={`bot-strategy-option${activeStrategy === s.id ? ' active' : ''}`}>
              <input
                type="checkbox"
                checked={activeStrategy === s.id}
                disabled={strategyLoading}
                onChange={() => handleStrategyChange(s.id)}
              />
              <span className="bot-strategy-option-text">
                <span className="bot-strategy-option-label">{s.label}</span>
                <span className="bot-strategy-option-desc">{s.description}</span>
              </span>
            </label>
          ))}
        </div>
      </div>

      <div className="bot-strategy-section">
        <div className="bot-strategy-title">Risk per trade</div>
        <p className="bot-strategy-hint">
          Applies from the next trade. Position size = capital × risk% ÷ SL distance.
        </p>
        <select
          className="bot-risk-select"
          value={activeRisk}
          disabled={riskLoading}
          onChange={(e) => handleRiskChange(e.target.value)}
        >
          {RISK_OPTIONS.map((n) => (
            <option key={n} value={n}>{n}%</option>
          ))}
        </select>
      </div>

      <div className="bot-strategy-section">
        <div className="bot-strategy-title">Max capital per trade</div>
        <p className="bot-strategy-hint">
          Caps share count so orders fit your balance. Applies from the next trade.
        </p>
        <div className="bot-strategy-options">
          {CAPITAL_USAGE_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className={`bot-strategy-option${activeCapitalUsage === opt.value ? ' active' : ''}`}
            >
              <input
                type="checkbox"
                checked={activeCapitalUsage === opt.value}
                disabled={capitalUsageLoading}
                onChange={() => handleCapitalUsageChange(opt.value)}
              />
              <span className="bot-strategy-option-text">
                <span className="bot-strategy-option-label">{opt.label}</span>
                <span className="bot-strategy-option-desc">{opt.description}</span>
              </span>
            </label>
          ))}
        </div>
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
