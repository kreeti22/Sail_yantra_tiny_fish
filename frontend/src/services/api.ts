import {
  BDIResponse,
  BunkerPricesResponse,
  MarketSummaryResponse,
  SyncResponse,
  SyncStatusResponse,
} from '../types/market';
import { OptimizationResponse, VoyageParameters } from '../types/optimizer';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || `HTTP Error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  async getBdi(forceRefresh: boolean = false): Promise<BDIResponse> {
    const url = `${BASE_URL}/api/market/bdi${forceRefresh ? '?force_refresh=true' : ''}`;
    const res = await fetch(url);
    return handleResponse<BDIResponse>(res);
  },

  async getBunkerPrices(forceRefresh: boolean = false): Promise<BunkerPricesResponse> {
    const url = `${BASE_URL}/api/market/bunker-prices${forceRefresh ? '?force_refresh=true' : ''}`;
    const res = await fetch(url);
    return handleResponse<BunkerPricesResponse>(res);
  },

  async getSyncStatus(): Promise<SyncStatusResponse> {
    const res = await fetch(`${BASE_URL}/api/market/sync/status`);
    return handleResponse<SyncStatusResponse>(res);
  },

  async triggerSync(target: string = 'all', force: boolean = false): Promise<SyncResponse> {
    const res = await fetch(`${BASE_URL}/api/market/sync`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ target, force }),
    });
    return handleResponse<SyncResponse>(res);
  },

  async getMarketSummary(): Promise<MarketSummaryResponse> {
    const res = await fetch(`${BASE_URL}/api/market/summary`);
    return handleResponse<MarketSummaryResponse>(res);
  },

  async runOptimization(
    params: VoyageParameters,
    useLiveMarket: boolean = true
  ): Promise<OptimizationResponse> {
    const url = `${BASE_URL}/api/optimizer/run?use_live_market=${useLiveMarket}`;
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(params),
    });
    return handleResponse<OptimizationResponse>(res);
  },
};
