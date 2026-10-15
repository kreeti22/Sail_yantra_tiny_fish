export interface BDIData {
  index_name: string;
  value: number;
  daily_change: number | null;
  daily_change_pct: number | null;
  reporting_date: string;
  unit: string;
}

export interface BDIResponse {
  status: string;
  freshness: 'fresh' | 'stale' | 'fallback' | 'error';
  data: BDIData;
  extracted_at: string | null;
  source_url: string;
  message?: string | null;
}

export interface BunkerFuelPrice {
  port_name: string;
  fuel_grade: string;
  price_usd_per_mt: number;
  daily_change: number | null;
  currency: string;
  unit: string;
  reporting_date: string | null;
}

export interface BunkerBenchmark {
  port_name: string;
  fuel_grade: string;
  price_usd_per_mt: number;
  reporting_date: string | null;
}

export interface BunkerPricesData {
  benchmark: BunkerBenchmark;
  ports: BunkerFuelPrice[];
}

export interface BunkerPricesResponse {
  status: string;
  freshness: 'fresh' | 'stale' | 'fallback' | 'error';
  data: BunkerPricesData;
  extracted_at: string | null;
  source_url: string;
  message?: string | null;
}

export interface SyncStatusResponse {
  status: string;
  is_syncing: boolean;
  last_sync_attempt: string | null;
  last_successful_sync: string | null;
  bdi_freshness: string;
  bdi_last_extracted: string | null;
  bunker_freshness: string;
  bunker_last_extracted: string | null;
  cache_file_exists: boolean;
  api_key_configured: boolean;
  last_error: string | null;
}

export interface SyncResponse {
  status: string;
  message: string;
  triggered_at: string;
  bdi_updated: boolean;
  bunker_updated: boolean;
  bdi_freshness: string;
  bunker_freshness: string;
  errors: string[];
}

export interface MarketSummaryResponse {
  status: string;
  bdi: BDIResponse;
  bunker: BunkerPricesResponse;
  ml_ready: boolean;
  timestamp: string;
}
