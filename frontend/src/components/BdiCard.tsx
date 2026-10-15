import React from 'react';
import { TrendingUp, TrendingDown, ExternalLink, Clock, AlertTriangle } from 'lucide-react';
import { BDIResponse } from '../types/market';

interface BdiCardProps {
  data: BDIResponse | null;
  loading: boolean;
  error: string | null;
}

export const BdiCard: React.FC<BdiCardProps> = ({ data, loading, error }) => {
  if (loading && !data) {
    return (
      <div className="terminal-card" style={{ height: '220px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p className="label-mono">Fetching latest Baltic Dry Index via TinyFish...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="terminal-card" style={{ height: '220px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-red)', marginBottom: '0.5rem' }}>
          <AlertTriangle size={18} />
          <span style={{ fontWeight: 600 }}>BDI Data Unavailable</span>
        </div>
        <p style={{ fontSize: '0.78rem', color: 'var(--fg-dim)' }}>{error}</p>
      </div>
    );
  }

  const bdi = data?.data;
  const isPositive = (bdi?.daily_change ?? 0) >= 0;
  const freshness = data?.freshness || 'fallback';

  const badgeClass =
    freshness === 'fresh' ? 'fresh' : freshness === 'stale' ? 'stale' : 'fallback';

  return (
    <div className="terminal-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
          <div>
            <div className="label-mono">Baltic Exchange Benchmark</div>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginTop: '0.1rem' }}>
              Baltic Dry Index (BDI)
            </h2>
          </div>
          <span className={`pill-badge ${badgeClass}`}>
            <span className="pulse-dot" />
            {freshness === 'fresh' ? 'LIVE SYNC' : freshness === 'stale' ? 'STALE CACHE' : 'CACHED BASELINE'}
          </span>
        </div>

        {/* Big Number Section */}
        <div style={{ margin: '1rem 0' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.85rem' }}>
            <span
              className="mono"
              style={{
                fontSize: '2.5rem',
                fontWeight: 700,
                letterSpacing: '-0.03em',
                lineHeight: 1,
                color: 'var(--fg)',
              }}
            >
              {bdi ? bdi.value.toLocaleString() : '1,550'}
            </span>
            <span className="mono" style={{ fontSize: '0.9rem', color: 'var(--fg-mute)' }}>
              POINTS
            </span>

            {bdi?.daily_change !== null && bdi?.daily_change !== undefined && (
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.2rem',
                  marginLeft: 'auto',
                  color: isPositive ? 'var(--accent-green)' : 'var(--accent-red)',
                  fontWeight: 600,
                  fontSize: '0.88rem',
                }}
                className="mono"
              >
                {isPositive ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                <span>
                  {isPositive ? '+' : ''}
                  {bdi.daily_change} pts
                </span>
                {bdi.daily_change_pct !== null && (
                  <span style={{ fontSize: '0.75rem', opacity: 0.85 }}>
                    ({isPositive ? '+' : ''}
                    {bdi.daily_change_pct}%)
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Market Context Details */}
        <div
          style={{
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            borderRadius: '3px',
            padding: '0.6rem 0.8rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '0.5rem',
            marginBottom: '0.85rem',
          }}
          className="mono"
        >
          <div>
            <div className="label-mono" style={{ fontSize: '0.6rem' }}>Reporting Date</div>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--fg)' }}>
              {bdi?.reporting_date || 'Current Session'}
            </div>
          </div>
          <div>
            <div className="label-mono" style={{ fontSize: '0.6rem' }}>Charter Impact</div>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--accent)' }}>
              {(bdi?.value ?? 1550) > 2000 ? 'High Rate Pressure' : 'Balanced Market'}
            </div>
          </div>
        </div>
      </div>

      {/* Footer Attribution & Freshness Metadata */}
      <div
        style={{
          borderTop: '1px solid var(--border)',
          paddingTop: '0.75rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.7rem',
          color: 'var(--fg-dim)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <Clock size={12} color="var(--fg-mute)" />
          <span>
            Extracted:{' '}
            {data?.extracted_at
              ? new Date(data.extracted_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : 'Default baseline'}
          </span>
        </div>

        <a
          href={data?.source_url || 'https://tradingeconomics.com/commodity/baltic'}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            color: 'var(--fg-mute)',
            textDecoration: 'none',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.25rem',
            fontSize: '0.68rem',
          }}
          className="mono"
        >
          <span>Trading Economics via TinyFish</span>
          <ExternalLink size={11} />
        </a>
      </div>
    </div>
  );
};
