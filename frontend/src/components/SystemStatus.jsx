import { useState, useEffect, useCallback } from 'react';
import { getSystemHealth } from '../api/client';
import './SystemStatus.css';

const WARN = '#f59e0b';

function formatRelativeTime(isoString) {
  if (!isoString) return null;
  const then = new Date(isoString).getTime();
  const mins = Math.floor((Date.now() - then) / 60000);
  if (mins < 1) return 'just now';
  if (mins === 1) return '1m ago';
  return `${mins}m ago`;
}

function StatusRow({ state, label, detail }) {
  const color =
    state === 'ok' ? 'var(--green)' :
    state === 'warn' ? WARN :
    state === 'error' ? 'var(--red)' :
    'var(--text-muted)';

  return (
    <div className="system-status-row">
      <span className="system-status-dot" style={{ background: color }} aria-hidden />
      <span className="system-status-label">{label}</span>
      <span className="system-status-detail">{detail}</span>
    </div>
  );
}

function marketState(market) {
  if (market?.status === 'open') return 'ok';
  if (market?.status === 'weekend' || market?.status === 'post_close') return 'warn';
  return 'warn';
}

function brokerState(broker) {
  if (!broker?.configured) return 'error';
  if (broker.probed && broker.connected) return 'ok';
  if (broker.probed && broker.connected === false) return 'error';
  return 'warn';
}

function brokerDetail(broker) {
  if (!broker?.configured) return broker?.error || 'Credentials missing in .env';
  if (broker.probed && broker.connected) return 'Connected';
  if (broker.probed && broker.connected === false) return broker.error || 'Login failed';
  return 'Not verified — click Refresh to test';
}

function celeryState(celery) {
  if (celery?.redis_ok && celery?.worker_ok) return 'ok';
  if (!celery?.redis_ok) return 'warn';
  return 'error';
}

function celeryDetail(celery) {
  if (celery?.redis_ok && celery?.worker_ok) {
    return `Redis OK · ${celery.worker_count} worker(s)`;
  }
  if (!celery?.redis_ok) return 'Redis unreachable — local-thread mode';
  return 'No Celery worker responding';
}

function beatState(beat) {
  if (beat?.ok === true) return 'ok';
  if (beat?.ok === false) return 'error';
  return 'warn';
}

function beatDetail(beat) {
  if (beat?.ok === true) return 'Active';
  if (beat?.ok === false) return beat.detail || 'Inactive';
  return beat?.detail || 'Unknown';
}

function ipState(ip) {
  if (ip?.status === 'ok') return 'ok';
  if (ip?.status === 'mismatch') return 'error';
  return 'warn';
}

function ipDetail(ip) {
  if (ip?.status === 'ok') return `${ip.expected} ✓`;
  if (ip?.status === 'mismatch') {
    return `Expected ${ip.expected}, got ${ip.actual}`;
  }
  return ip?.error || 'Could not verify';
}

function botState(bot) {
  if (bot?.is_running && bot?.stale) return 'error';
  if (bot?.is_running) return 'ok';
  return 'warn';
}

function botDetail(bot) {
  if (bot?.is_running) {
    const rel = formatRelativeTime(bot.last_heartbeat_at);
    if (bot.stale) return `Stale · last ping ${rel || 'never'}`;
    return `Running · last ping ${rel || 'just now'}`;
  }
  return 'Stopped';
}

export default function SystemStatus({ probeTrigger = 0 }) {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async (probe = false) => {
    setLoading(true);
    setError('');
    try {
      const { data } = await getSystemHealth(probe);
      setHealth(data);
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Failed to load system status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(false);
    const id = setInterval(() => load(false), 60000);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => {
    if (probeTrigger > 0) {
      load(true);
    }
  }, [probeTrigger, load]);

  const checkedLabel = health?.checked_at
    ? new Date(health.checked_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
    : null;

  return (
    <div className="system-status card">
      <div className="system-status-header">
        <div>
          <div className="system-status-title">System Status</div>
          <div className="system-status-sub">VPS, broker, and bot health at a glance</div>
        </div>
        {health?.overall && (
          <span className={`system-status-overall system-status-overall--${health.overall}`}>
            {health.overall}
          </span>
        )}
      </div>

      {error && <div className="system-status-error">{error}</div>}

      {health && (
        <div className="system-status-rows">
          <StatusRow
            state={marketState(health.market)}
            label="Market"
            detail={`${health.market?.label || '—'} · ${health.market?.session || ''}`}
          />
          <StatusRow
            state={brokerState(health.broker)}
            label="Broker"
            detail={brokerDetail(health.broker)}
          />
          <StatusRow
            state={celeryState(health.celery)}
            label="Celery worker"
            detail={celeryDetail(health.celery)}
          />
          <StatusRow
            state={beatState(health.celery_beat)}
            label="Celery Beat"
            detail={beatDetail(health.celery_beat)}
          />
          <StatusRow
            state={ipState(health.ip)}
            label="Angel One IP"
            detail={ipDetail(health.ip)}
          />
          <StatusRow
            state={botState(health.bot)}
            label="Bot heartbeat"
            detail={botDetail(health.bot)}
          />
        </div>
      )}

      {!health && !error && loading && (
        <div className="system-status-loading">Loading status…</div>
      )}

      <div className="system-status-footer">
        {checkedLabel && <span>Checked: {checkedLabel}</span>}
        {loading && health && <span>Updating…</span>}
        {!health?.broker?.probed && health?.broker?.configured && (
          <span className="system-status-hint">Broker login tested on Dashboard Refresh only</span>
        )}
      </div>
    </div>
  );
}
