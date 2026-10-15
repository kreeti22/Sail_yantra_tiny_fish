import React, { useState } from 'react';
import { Compass, Play } from 'lucide-react';
import { OptimizationResponse, VoyageParameters } from '../types/optimizer';
import { api } from '../services/api';

interface VoyageOptimizerProps {
  liveBdi: number;
  liveBunkerPrice: number;
}

export const VoyageOptimizer: React.FC<VoyageOptimizerProps> = ({ liveBdi, liveBunkerPrice }) => {
  const [params, setParams] = useState<VoyageParameters>({
    route: 'Dampier, Australia - Visakhapatnam',
    cargo_type: 'Coal Ore',
    vessel_class: 'Panamax',
    market_event: 'None',
    vessel_dwt: 78000,
    distance_nm: 3570,
    port_congestion_days: 1.5,
    port: 'Vizag',
    cargo_tonnes: 60000,
    required_days: 30,
    wind_speed: 12.0,
    wave_height: 2.0,
    speed: 14.0,
    vessel_age: 8,
    inventory_hold_cost_per_day: 12000,
  });

  const [useLiveMarket, setUseLiveMarket] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<OptimizationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const voyageInputs = {
        ...params,
        baltic_style_index: useLiveMarket ? liveBdi : params.baltic_style_index,
        bunker_fuel_price: useLiveMarket ? liveBunkerPrice : params.bunker_fuel_price,
      };
      const res = await api.runOptimization(voyageInputs, useLiveMarket);
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Optimization execution failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="terminal-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div
            style={{
              background: 'var(--bg-elevated)',
              padding: '0.45rem',
              borderRadius: '4px',
              border: '1px solid var(--border)',
              display: 'flex',
            }}
          >
            <Compass size={18} color="var(--accent)" />
          </div>
          <div>
            <div className="label-mono">Decision Support Engine</div>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, marginTop: '0.1rem' }}>
              SAIL Charter Timing & Landed Cost Optimizer
            </h2>
          </div>
        </div>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            cursor: 'pointer',
            fontSize: '0.75rem',
          }}
          className="mono"
        >
          <input
            type="checkbox"
            checked={useLiveMarket}
            onChange={(e) => setUseLiveMarket(e.target.checked)}
            style={{ width: 'auto' }}
          />
          <span style={{ fontWeight: 600, color: useLiveMarket ? 'var(--accent-green)' : 'var(--fg-dim)' }}>
            AUTO-INJECT LIVE TINYFISH MARKET INTELLIGENCE
          </span>
        </label>
      </div>

      {/* Grid Inputs */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '0.85rem',
          marginBottom: '1.25rem',
        }}
      >
        <div>
          <label className="label-mono">Trade Route</label>
          <select
            value={params.route}
            onChange={(e) => setParams({ ...params, route: e.target.value })}
          >
            <option value="Dampier, Australia - Visakhapatnam">Dampier - Visakhapatnam</option>
            <option value="Gladstone, Australia - Haldia">Gladstone - Haldia</option>
            <option value="Richards Bay, South Africa - Paradip">Richards Bay - Paradip</option>
            <option value="Newcastle, Australia - Ennore">Newcastle - Ennore</option>
          </select>
        </div>

        <div>
          <label className="label-mono">Commodity Type</label>
          <select
            value={params.cargo_type}
            onChange={(e) => setParams({ ...params, cargo_type: e.target.value })}
          >
            <option value="Coal Ore">Coal Ore (Coking)</option>
            <option value="Iron Ore">Iron Ore</option>
            <option value="Limestone">Limestone</option>
          </select>
        </div>

        <div>
          <label className="label-mono">Vessel Class</label>
          <select
            value={params.vessel_class}
            onChange={(e) => setParams({ ...params, vessel_class: e.target.value })}
          >
            <option value="Panamax">Panamax (65k–100k DWT)</option>
            <option value="Capesize">Capesize (100k–250k DWT)</option>
            <option value="Supramax">Supramax (40k–65k DWT)</option>
            <option value="Handysize">Handysize (15k–40k DWT)</option>
          </select>
        </div>

        <div>
          <label className="label-mono">Applied BDI Index</label>
          <input
            type="number"
            disabled={useLiveMarket}
            value={useLiveMarket ? liveBdi : params.baltic_style_index ?? liveBdi}
            onChange={(e) => setParams({ ...params, baltic_style_index: Number(e.target.value) })}
          />
        </div>

        <div>
          <label className="label-mono">Bunker Price (USD/MT)</label>
          <input
            type="number"
            disabled={useLiveMarket}
            value={useLiveMarket ? liveBunkerPrice : params.bunker_fuel_price ?? liveBunkerPrice}
            onChange={(e) => setParams({ ...params, bunker_fuel_price: Number(e.target.value) })}
          />
        </div>
      </div>

      <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'center', marginBottom: '1.25rem' }}>
        <button
          onClick={handleRun}
          disabled={loading}
          className="btn-terminal btn-primary"
          style={{ padding: '0.65rem 1.4rem', fontSize: '0.82rem' }}
        >
          <Play size={14} />
          <span>{loading ? 'CALCULATING PIPELINE...' : 'RUN FREIGHT & CHARTER OPTIMIZATION'}</span>
        </button>

        {useLiveMarket && (
          <span className="mono" style={{ fontSize: '0.72rem', color: 'var(--fg-dim)' }}>
            ✓ Using live BDI ({liveBdi}) and Singapore VLSFO (${liveBunkerPrice}/MT) from TinyFish
          </span>
        )}
      </div>

      {error && (
        <div style={{ padding: '0.75rem', background: 'rgba(201, 123, 123, 0.1)', color: 'var(--accent-red)', borderRadius: '3px', marginBottom: '1rem', fontSize: '0.8rem' }}>
          {error}
        </div>
      )}

      {/* Results Display */}
      {result && (
        <div
          style={{
            borderTop: '1px solid var(--border)',
            paddingTop: '1.25rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '1rem',
          }}
        >
          {/* Recommendation Card */}
          <div
            style={{
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-strong)',
              borderRadius: '4px',
              padding: '1rem',
            }}
          >
            <div className="label-mono" style={{ marginBottom: '0.3rem' }}>Charter Timing Decision</div>
            <div
              style={{
                fontSize: '1.05rem',
                fontWeight: 700,
                color: result.decision === 'EXECUTE_NOW' ? 'var(--accent-green)' : 'var(--accent-amber)',
                marginBottom: '0.5rem',
              }}
            >
              {result.decision_label}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--fg-dim)', marginBottom: '0.8rem' }}>
              Target Execution: <span className="mono" style={{ fontWeight: 700, color: 'var(--fg)' }}>T+{result.optimal_t_star} days</span>
            </div>
            <div
              className="mono"
              style={{
                fontSize: '1.4rem',
                fontWeight: 700,
                color: 'var(--accent-green)',
              }}
            >
              ${result.net_savings_usd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              <span style={{ fontSize: '0.72rem', color: 'var(--fg-mute)', marginLeft: '0.35rem' }}>
                EXPECTED SAVINGS
              </span>
            </div>
          </div>

          {/* TLC Breakdown */}
          <div
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              padding: '1rem',
            }}
          >
            <div className="label-mono" style={{ marginBottom: '0.5rem' }}>Total Landed Cost (TLC) Breakdown</div>
            <div className="mono" style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--fg-dim)' }}>Base Freight Rate:</span>
                <span style={{ fontWeight: 600 }}>${result.tlc_breakdown.base_freight.toLocaleString()}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--fg-dim)' }}>Bunker Fuel Surcharge:</span>
                <span style={{ fontWeight: 600 }}>${result.tlc_breakdown.bunker_surcharge.toLocaleString()}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--fg-dim)' }}>Demurrage Risk Exposure:</span>
                <span style={{ fontWeight: 600 }}>${result.tlc_breakdown.demurrage_risk.toLocaleString()}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--fg-dim)' }}>Inventory Carrying Cost:</span>
                <span style={{ fontWeight: 600 }}>${result.tlc_breakdown.inventory_hold.toLocaleString()}</span>
              </div>
              <div
                style={{
                  borderTop: '1px solid var(--border-strong)',
                  paddingTop: '0.35rem',
                  marginTop: '0.2rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  fontWeight: 700,
                  fontSize: '0.92rem',
                  color: 'var(--accent)',
                }}
              >
                <span>Total Landed Cost:</span>
                <span>${result.tlc_breakdown.total_landed_cost.toLocaleString()}</span>
              </div>
            </div>
          </div>

          {/* 14-day Forward Rates */}
          {result.freight_forecast && result.freight_forecast.dates && (
            <div
              style={{
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                padding: '1rem',
              }}
            >
              <div className="label-mono" style={{ marginBottom: '0.5rem' }}>14-Day Freight Trend Projection</div>
              <div style={{ overflowX: 'auto', maxHeight: '140px' }}>
                <table className="terminal-table" style={{ fontSize: '0.72rem' }}>
                  <thead>
                    <tr>
                      <th>Day</th>
                      <th>Expected $/T</th>
                      <th>Range (±1σ)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.freight_forecast.dates.slice(0, 5).map((d, i) => (
                      <tr key={d}>
                        <td>T+{i}</td>
                        <td style={{ fontWeight: 700 }}>${result.freight_forecast.mean?.[i]?.toFixed(2)}</td>
                        <td style={{ color: 'var(--fg-mute)' }}>
                          ${result.freight_forecast.lower?.[i]?.toFixed(1)} – ${result.freight_forecast.upper?.[i]?.toFixed(1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
