import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  CandlestickSeries,
  LineStyle,
  ColorType,
} from 'lightweight-charts';
import './StockChart.css';

const CHART_HEIGHT = 220;

function toUtcTimestamp(iso) {
  return Math.floor(new Date(iso).getTime() / 1000);
}

function candlesToSeriesData(candles) {
  const byTime = new Map();
  for (const c of candles || []) {
    const time = toUtcTimestamp(c.time);
    if (Number.isNaN(time)) continue;
    byTime.set(time, {
      time,
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
    });
  }
  return [...byTime.values()].sort((a, b) => a.time - b.time);
}

export default function StockChart({
  symbol,
  candles,
  orbHigh,
  orbLow,
  lastClose,
  error,
  liveTick,
}) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const pendingTickRef = useRef(null);
  const [displayLtp, setDisplayLtp] = useState(lastClose);

  const applyLiveTick = (tick) => {
    if (!tick?.bar || !seriesRef.current) return false;
    const b = tick.bar;
    seriesRef.current.update({
      time: b.time,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    });
    if (tick.ltp != null) setDisplayLtp(tick.ltp);
    return true;
  };

  const hasOrb = orbHigh != null && orbLow != null;
  const seriesData = candlesToSeriesData(candles);
  const hasData = seriesData.length > 0;

  useEffect(() => {
    setDisplayLtp(lastClose);
  }, [lastClose, symbol]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !hasData) return undefined;

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: '#1a1d27' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#2d3148' },
        horzLines: { color: '#2d3148' },
      },
      width: el.clientWidth,
      height: CHART_HEIGHT,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: '#2d3148',
      },
      rightPriceScale: {
        borderColor: '#2d3148',
      },
      crosshair: {
        vertLine: { color: '#4f8ef7', labelBackgroundColor: '#22263a' },
        horzLine: { color: '#4f8ef7', labelBackgroundColor: '#22263a' },
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    series.setData(seriesData);

    if (hasOrb) {
      series.createPriceLine({
        price: Number(orbHigh),
        color: '#22c55e',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'ORB High',
      });
      series.createPriceLine({
        price: Number(orbLow),
        color: '#ef4444',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: 'ORB Low',
      });
    }

    chart.timeScale().fitContent();

    chartRef.current = chart;
    seriesRef.current = series;

    if (pendingTickRef.current) {
      applyLiveTick(pendingTickRef.current);
      pendingTickRef.current = null;
    } else if (liveTick) {
      applyLiveTick(liveTick);
    }

    const handleResize = () => {
      if (el) chart.applyOptions({ width: el.clientWidth });
    };
    const ro = new ResizeObserver(handleResize);
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [symbol, candles, orbHigh, orbLow, hasOrb, hasData]);

  useEffect(() => {
    if (!liveTick?.bar) return;
    if (!applyLiveTick(liveTick)) {
      pendingTickRef.current = liveTick;
      if (liveTick.ltp != null) setDisplayLtp(liveTick.ltp);
    }
  }, [liveTick]);

  return (
    <div className="stock-chart-card card">
      <div className="stock-chart-header">
        <span className="stock-chart-symbol">{symbol}</span>
        {displayLtp != null && (
          <span className="stock-chart-ltp stock-chart-ltp-live">
            ₹{Number(displayLtp).toFixed(2)}
          </span>
        )}
      </div>
      {hasOrb && (
        <div className="stock-chart-orb">
          <span className="orb-high">ORB High ₹{Number(orbHigh).toFixed(2)}</span>
          <span className="orb-low">ORB Low ₹{Number(orbLow).toFixed(2)}</span>
        </div>
      )}

      {error && !hasData ? (
        <div className="stock-chart-empty">{error}</div>
      ) : !hasData ? (
        <div className="stock-chart-empty">{error || 'No candle data'}</div>
      ) : (
        <>
          {error && <div className="stock-chart-warn">{error}</div>}
          <div
            ref={containerRef}
            className="stock-chart-container"
            style={{ height: CHART_HEIGHT }}
          />
        </>
      )}
    </div>
  );
}
