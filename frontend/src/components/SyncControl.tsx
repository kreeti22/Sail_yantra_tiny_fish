import React, { useState } from 'react';
import { RefreshCw, CheckCircle2, AlertCircle, Info, Database } from 'lucide-react';
import { SyncStatusResponse } from '../types/market';
import { api } from '../services/api';

interface SyncControlProps {
  status: SyncStatusResponse | null;
  onSyncComplete: () => void;
}

export const SyncControl: React.FC<SyncControlProps> = ({ status, onSyncComplete }) => {
  const [syncing, setSyncing] = useState<boolean>(false);
  const [msg, setMsg] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);

  const handleSync = async (force: boolean = false) => {
    setSyncing(true);
    setMsg(null);
    try {
      const res = await api.triggerSync('all', force);
      setMsg({
        text: res.message || 'Synchronization completed successfully.',
        type: res.status === 'success' ? 'success' : 'info',
      });
      onSyncComplete();
    } catch (err: any) {
      setMsg({
        text: err.message || 'Sync failed. Server preserved cached data.',
        type: 'error',
      });
    } finally {
      setSyncing(false);
      setTimeout(() => setMsg(null), 8000);
    }
  };

  const isConfigured = status?.api_key_configured ?? false;

  return (
    <div
      className="terminal-card"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem',
        background: 'var(--bg-elevated)',
        borderColor: 'var(--border-strong)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
        <div
          style={{
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            borderRadius: '4px',
            padding: '0.5rem',
            display: 'flex',
          }}
        >
          <Database size={18} color="var(--accent)" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>TinyFish Market Agent Sync Desk</span>
            <span
              className={`pill-badge ${isConfigured ? 'fresh' : 'fallback'}`}
              style={{ fontSize: '0.62rem' }}
            >
              {isConfigured ? 'LIVE AGENT ACTIVE' : 'CACHED PERSISTENCE MODE'}
            </span>
          </div>
          <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--fg-dim)' }}>
            {status?.last_successful_sync
              ? `Last Synced: ${new Date(status.last_successful_sync).toLocaleTimeString()} · Cache: data/market_cache.json`
              : 'Persistence active · Baseline loaded'}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        {msg && (
          <div
            className="mono"
            style={{
              fontSize: '0.72rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              color:
                msg.type === 'success'
                  ? 'var(--accent-green)'
                  : msg.type === 'error'
                  ? 'var(--accent-red)'
                  : 'var(--accent-amber)',
            }}
          >
            {msg.type === 'success' && <CheckCircle2 size={14} />}
            {msg.type === 'error' && <AlertCircle size={14} />}
            {msg.type === 'info' && <Info size={14} />}
            <span>{msg.text}</span>
          </div>
        )}

        <button
          onClick={() => handleSync(false)}
          disabled={syncing || status?.is_syncing}
          className="btn-terminal btn-primary"
        >
          <RefreshCw size={13} className={syncing || status?.is_syncing ? 'pulse-dot' : ''} />
          <span>{syncing ? 'EXTRACTING VIA TINYFISH...' : 'SYNC MARKET INTELLIGENCE'}</span>
        </button>

        <button
          onClick={() => handleSync(true)}
          disabled={syncing}
          className="btn-terminal"
          style={{ fontSize: '0.68rem', padding: '0.55rem 0.65rem' }}
          title="Force refresh bypassing TTL"
        >
          FORCE REFRESH
        </button>
      </div>
    </div>
  );
};
