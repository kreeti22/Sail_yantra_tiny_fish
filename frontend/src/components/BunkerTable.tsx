import React, { useState } from 'react';
import { Fuel, ExternalLink, Clock, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';
import { BunkerPricesResponse } from '../types/market';

interface BunkerTableProps {
  data: BunkerPricesResponse | null;
  loading: boolean;
  error: string | null;
}

export const BunkerTable: React.FC<BunkerTableProps> = ({ data, loading, error }) => {
  const [selectedPort, setSelectedPort] = useState<string>('ALL');

  if (loading && !data) {
    return (
      <div className="terminal-card" style={{ height: '340px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p className="label-mono">Fetching latest marine bunker fuel quotes via TinyFish...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="terminal-card" style={{ height: '340px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-red)', marginBottom: '0.5rem' }}>
          <AlertTriangle size={18} />
          <span style={{ fontWeight: 600 }}>Bunker Fuel Quotes Unavailable</span>
        </div>
        <p style={{ fontSize: '0.78rem', color: 'var(--fg-dim)' }}>{error}</p>
      </div>
    );
  }

  const bunkerData = data?.data;
  const benchmark = bunkerData?.benchmark;
  const portsList = bunkerData?.ports || [];
  const freshness = data?.freshness || 'fallback';

  const uniquePorts = ['ALL', ...Array.from(new Set(portsList.map((p) => p.port_name)))];

  const filteredQuotes =
    selectedPort === 'ALL'
      ? portsList
      : portsList.filter((p) => p.port_name === selectedPort);

  return (
    <div className="terminal-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.85rem' }}>
        <div>
          <div className="label-mono">Marine Fuel Intelligence</div>
          <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginTop: '0.1rem' }}>
            Global Bunker Fuel Prices (USD / Metric Ton)
          </h2>
        </div>
        <span className={`pill-badge ${freshness === 'fresh' ? 'fresh' : freshness === 'stale' ? 'stale' : 'fallback'}`}>
          <span className="pulse-dot" />
          {freshness === 'fresh' ? 'LIVE SYNC' : freshness === 'stale' ? 'STALE CACHE' : 'CACHED BASELINE'}
        </span>
      </div>

      {/* Benchmark Highlight Card */}
      {benchmark && (
        <div
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-strong)',
            borderRadius: '4px',
            padding: '0.75rem 1rem',
            marginBottom: '1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div
              style={{
                background: 'var(--bg)',
                padding: '0.4rem',
                borderRadius: '3px',
                border: '1px solid var(--border)',
                display: 'flex',
              }}
            >
              <Fuel size={16} color="var(--accent)" />
            </div>
            <div>
              <div className="label-mono" style={{ fontSize: '0.62rem' }}>
                Chartering Benchmark Fuel
              </div>
              <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                {benchmark.port_name} · {benchmark.fuel_grade}
              </div>
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <div className="label-mono" style={{ fontSize: '0.6rem' }}>
              Base Surcharge Metric
            </div>
            <div
              className="mono"
              style={{
                fontSize: '1.35rem',
                fontWeight: 700,
                color: 'var(--fg)',
                letterSpacing: '-0.02em',
              }}
            >
              ${benchmark.price_usd_per_mt.toFixed(1)}
              <span style={{ fontSize: '0.75rem', color: 'var(--fg-mute)', marginLeft: '0.3rem' }}>
                / MT
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Port Filter Tabs */}
      <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.85rem', flexWrap: 'wrap' }}>
        {uniquePorts.map((p) => (
          <button
            key={p}
            onClick={() => setSelectedPort(p)}
            className="btn-terminal"
            style={{
              padding: '0.25rem 0.6rem',
              fontSize: '0.68rem',
              background: selectedPort === p ? 'var(--accent)' : 'var(--bg)',
              color: selectedPort === p ? 'var(--bg)' : 'var(--fg)',
              borderColor: selectedPort === p ? 'var(--accent)' : 'var(--border)',
            }}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Quotes Table */}
      <div style={{ overflowX: 'auto', marginBottom: '0.85rem' }}>
        <table className="terminal-table">
          <thead>
            <tr>
              <th>Port</th>
              <th>Fuel Grade</th>
              <th>Price (USD/MT)</th>
              <th>24h Change</th>
              <th>Reporting Date</th>
            </tr>
          </thead>
          <tbody>
            {filteredQuotes.map((q, idx) => {
              const isPos = (q.daily_change ?? 0) >= 0;
              return (
                <tr key={`${q.port_name}-${q.fuel_grade}-${idx}`}>
                  <td style={{ fontWeight: 600 }}>{q.port_name}</td>
                  <td>
                    <span
                      style={{
                        padding: '0.15rem 0.4rem',
                        borderRadius: '2px',
                        background: 'var(--bg)',
                        border: '1px solid var(--border)',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                      }}
                    >
                      {q.fuel_grade}
                    </span>
                  </td>
                  <td style={{ fontWeight: 700 }}>${q.price_usd_per_mt.toFixed(1)}</td>
                  <td>
                    {q.daily_change !== null && q.daily_change !== undefined ? (
                      <span
                        style={{
                          color: isPos ? 'var(--accent-red)' : 'var(--accent-green)', // fuel price rise is red (cost increase)
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.2rem',
                        }}
                      >
                        {isPos ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                        {isPos ? '+' : ''}
                        {q.daily_change}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--fg-mute)' }}>—</span>
                    )}
                  </td>
                  <td style={{ color: 'var(--fg-dim)' }}>{q.reporting_date || 'Latest'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer Attribution */}
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
          href={data?.source_url || 'https://shipandbunker.com/prices'}
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
          <span>Ship & Bunker via TinyFish</span>
          <ExternalLink size={11} />
        </a>
      </div>
    </div>
  );
};
