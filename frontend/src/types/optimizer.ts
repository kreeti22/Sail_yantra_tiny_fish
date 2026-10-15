export interface VoyageParameters {
  route: string;
  cargo_type: string;
  vessel_class: string;
  market_event: string;
  vessel_dwt: number;
  distance_nm: number;
  port_congestion_days: number;
  port: string;
  cargo_tonnes: number;
  required_days: number;
  wind_speed: number;
  wave_height: number;
  speed: number;
  vessel_age: number;
  inventory_hold_cost_per_day: number;
  baltic_style_index?: number | null;
  bunker_fuel_price?: number | null;
}

export interface TlcBreakdown {
  base_freight: number;
  bunker_surcharge: number;
  demurrage_risk: number;
  inventory_hold: number;
  total_landed_cost: number;
}

export interface ForecastData {
  dates: string[];
  mean?: number[];
  lower?: number[];
  upper?: number[];
  price?: number[];
}

export interface MarketProvenance {
  live_market_used: boolean;
  applied_bdi: number;
  applied_bunker_usd_mt: number;
  market_metadata?: any;
}

export interface OptimizationResponse {
  decision: string;
  decision_label: string;
  optimal_t_star: number;
  net_savings_usd: number;
  tlc_breakdown: TlcBreakdown;
  freight_forecast: ForecastData;
  fuel_forecast: ForecastData;
  market_provenance: MarketProvenance;
  speed_opt?: any;
  timing_decision?: any;
}
