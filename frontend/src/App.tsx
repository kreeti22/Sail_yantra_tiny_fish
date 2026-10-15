import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { BdiCard } from './components/BdiCard';
import { BunkerTable } from './components/BunkerTable';
import { SyncControl } from './components/SyncControl';
import { VoyageOptimizer } from './components/VoyageOptimizer';
import { BDIResponse, BunkerPricesResponse, SyncStatusResponse } from './types/market';
import { api } from './services/api';

export const App: React.FC = () => {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [bdi, setBdi] = useState<BDIResponse | null>(null);
  const [bunker, setBunker] = useState<BunkerPricesResponse | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [bdiRes, bunkerRes, statusRes] = await Promise.allSettled([
        api.getBdi(),
        api.getBunkerPrices(),
        api.getSyncStatus(),
      ]);

      if (bdiRes.status === 'fulfilled') {
        setBdi(bdiRes.value);
      }
      if (bunkerRes.status === 'fulfilled') {
        setBunker(bunkerRes.value);
      }
      if (statusRes.status === 'fulfilled') {
        setSyncStatus(statusRes.value);
      }
    } catch (err: any) {
      setError(err.message || 'Error communicating with SAIL YANTRA backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // Background polling every 60 seconds to keep fresh
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, []);

  const liveBdi = bdi?.data?.value ?? 1550;
  const liveBunker = bunker?.data?.benchmark?.price_usd_per_mt ?? 640;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header
        theme={theme}
        onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        bdiFreshness={bdi?.freshness || 'fallback'}
        bunkerFreshness={bunker?.freshness || 'fallback'}
      />

      <main style={{ flex: 1, padding: '1.5rem 1.75rem', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
        {/* Top Control Bar */}
        <div style={{ marginBottom: '1.25rem' }}>
          <SyncControl status={syncStatus} onSyncComplete={loadData} />
        </div>

        {/* 2-Column Market Intelligence Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
            gap: '1.25rem',
            marginBottom: '1.25rem',
          }}
        >
          <BdiCard data={bdi} loading={loading} error={error} />
          <BunkerTable data={bunker} loading={loading} error={error} />
        </div>

        {/* Voyage & Freight Optimizer */}
        <div style={{ marginBottom: '1.5rem' }}>
          <VoyageOptimizer liveBdi={liveBdi} liveBunkerPrice={liveBunker} />
        </div>
      </main>

      <footer
        style={{
          borderTop: '1px solid var(--border)',
          padding: '1.25rem 1.75rem',
          background: 'var(--bg-surface)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          fontSize: '0.72rem',
          color: 'var(--fg-mute)',
        }}
        className="mono"
      >
        <div>
          <span>SAIL YANTRA · Autonomous Maritime Chartering Desk</span>
          <span style={{ margin: '0 0.5rem' }}>·</span>
          <span>Powered by TinyFish Web Agents</span>
        </div>
        <div>
          <span>Backend: FastAPI (Port 8000)</span>
          <span style={{ margin: '0 0.5rem' }}>·</span>
          <span>Cache: JSON Atomic Persistence</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
