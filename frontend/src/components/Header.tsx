import React, { useEffect, useState } from 'react';
import { Anchor, Sun, Moon } from 'lucide-react';

interface HeaderProps {
  theme: 'dark' | 'light';
  onToggleTheme: () => void;
  bdiFreshness: string;
  bunkerFreshness: string;
}

export const Header: React.FC<HeaderProps> = ({
  theme,
  onToggleTheme,
  bdiFreshness,
  bunkerFreshness,
}) => {
  const [timeStr, setTimeStr] = useState<string>('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleDateString('en-GB', {
          day: '2-digit',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          timeZoneName: 'short',
        })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const isMarketLive = bdiFreshness === 'fresh' && bunkerFreshness === 'fresh';

  return (
    <header
      style={{
        borderBottom: '1px solid var(--border)',
        padding: '0.9rem 1.75rem',
        background: 'var(--bg-surface)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
        <div
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-strong)',
            padding: '0.45rem',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Anchor size={20} color="var(--accent)" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <h1 style={{ fontSize: '1.05rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
              SAIL YANTRA
            </h1>
            <span className="pill-badge fallback" style={{ fontSize: '0.6rem' }}>
              PROD v2.5 · TINYFISH
            </span>
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--fg-dim)' }}>
            Maritime Freight & Commercial Chartering Decision Support Desk
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
        <div
          className="mono"
          style={{
            fontSize: '0.7rem',
            color: 'var(--fg-dim)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.8rem',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
            <span
              className="pulse-dot"
              style={{ color: isMarketLive ? 'var(--accent-green)' : 'var(--accent-amber)' }}
            />
            BDI {bdiFreshness.toUpperCase()}
          </span>
          <span>·</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
            <span
              className="pulse-dot"
              style={{ color: bunkerFreshness === 'fresh' ? 'var(--accent-green)' : 'var(--accent-amber)' }}
            />
            BUNKER {bunkerFreshness.toUpperCase()}
          </span>
          <span>·</span>
          <span>{timeStr}</span>
        </div>

        <button
          onClick={onToggleTheme}
          className="btn-terminal"
          style={{ padding: '0.4rem 0.65rem' }}
          title="Toggle Light/Dark Theme"
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          <span style={{ fontSize: '0.7rem' }}>{theme === 'dark' ? 'LIGHT' : 'DARK'}</span>
        </button>
      </div>
    </header>
  );
};
