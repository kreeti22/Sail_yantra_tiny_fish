import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from '../services/api';

describe('Frontend API Client Service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches BDI data with correct URL and response mapping', async () => {
    const mockBdi = {
      status: 'success',
      freshness: 'fresh',
      data: {
        index_name: 'Baltic Dry Index',
        value: 1845.0,
        daily_change: 23.5,
        daily_change_pct: 1.29,
        reporting_date: '2026-10-14',
        unit: 'points',
      },
      extracted_at: '2026-10-15T06:00:00Z',
      source_url: 'https://tradingeconomics.com/commodity/baltic',
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockBdi,
    } as Response);

    const result = await api.getBdi(false);
    expect(result.status).toBe('success');
    expect(result.freshness).toBe('fresh');
    expect(result.data.value).toBe(1845.0);
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/market/bdi');
  });

  it('fetches Bunker prices with Singapore benchmark', async () => {
    const mockBunker = {
      status: 'success',
      freshness: 'fresh',
      data: {
        benchmark: {
          port_name: 'Singapore',
          fuel_grade: 'VLSFO',
          price_usd_per_mt: 648.5,
          reporting_date: '2026-10-14',
        },
        ports: [
          {
            port_name: 'Singapore',
            fuel_grade: 'VLSFO',
            price_usd_per_mt: 648.5,
            daily_change: -3.0,
            currency: 'USD',
            unit: 'USD/MT',
            reporting_date: '2026-10-14',
          },
        ],
      },
      extracted_at: '2026-10-15T06:00:00Z',
      source_url: 'https://shipandbunker.com/prices',
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockBunker,
    } as Response);

    const result = await api.getBunkerPrices(false);
    expect(result.data.benchmark.port_name).toBe('Singapore');
    expect(result.data.benchmark.price_usd_per_mt).toBe(648.5);
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/market/bunker-prices');
  });

  it('triggers manual sync with target and force parameters', async () => {
    const mockSync = {
      status: 'success',
      message: 'Sync completed.',
      triggered_at: '2026-10-15T06:00:00Z',
      bdi_updated: true,
      bunker_updated: true,
      bdi_freshness: 'fresh',
      bunker_freshness: 'fresh',
      errors: [],
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockSync,
    } as Response);

    const res = await api.triggerSync('all', true);
    expect(res.bdi_updated).toBe(true);
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/market/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: 'all', force: true }),
    });
  });

  it('handles backend HTTP errors gracefully', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      statusText: 'Too Many Requests',
      json: async () => ({ detail: 'Manual sync requested too soon. Please wait 25s.' }),
    } as Response);

    await expect(api.triggerSync()).rejects.toThrow('Manual sync requested too soon. Please wait 25s.');
  });
});
