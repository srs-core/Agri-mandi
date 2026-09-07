import React, { useEffect, useState } from 'react';
import {
  api,
  type BuyerRecommendationResponse,
  type Commodity,
  type EconomicOptionBreakdown,
  type ProduceLotSummary,
} from '../api/client';
import { useAuth } from '../context/AuthContext';

interface RecommendationViewProps {
  initialLotId?: string;
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const RecommendationView: React.FC<RecommendationViewProps> = ({ initialLotId, onNavigate }) => {
  const { profile } = useAuth();
  const [myLots, setMyLots] = useState<ProduceLotSummary[]>([]);
  const [commodities, setCommodities] = useState<Commodity[]>([]);

  // Form State
  const [selectedLotId, setSelectedLotId] = useState<string>(initialLotId || '');
  const [commodityId, setCommodityId] = useState<string>('');
  const [commodityName, setCommodityName] = useState<string>('');
  const [quantityQuintals, setQuantityQuintals] = useState<number>(30);
  const [qualityGrade, setQualityGrade] = useState<string>('Standard');
  const [pickupLocationName, setPickupLocationName] = useState<string>(
    profile?.primary_location ? `${profile.primary_location.name}, ${profile.primary_location.district}` : 'Pune Rural'
  );
  const [availabilityDate, setAvailabilityDate] = useState<string>(new Date().toISOString().split('T')[0]);

  // Query state
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [recommendationResult, setRecommendationResult] = useState<BuyerRecommendationResponse | null>(null);

  const applyLotToForm = (lot: ProduceLotSummary) => {
    setSelectedLotId(lot.id);
    setCommodityId(lot.commodity_id);
    setCommodityName(lot.commodity_name);
    const qtl = lot.unit.toLowerCase() === 'kg' ? Math.round((lot.available_quantity / 100) * 10) / 10 : lot.available_quantity;
    setQuantityQuintals(Math.max(qtl, 1));
    setQualityGrade(lot.quality_grade || 'Standard');
    if (lot.pickup_location) {
      setPickupLocationName(`${lot.pickup_location.name}, ${lot.pickup_location.district || lot.pickup_location.state}`);
    }
  };

  useEffect(() => {
    const loadInitialData = async () => {
      try {
        const [lots, comms] = await Promise.all([
          api.getMyProduceLots(),
          api.getCommodities(),
        ]);
        setMyLots(lots);
        setCommodities(comms);

        if (initialLotId) {
          const match = lots.find((l) => l.id === initialLotId);
          if (match) {
            applyLotToForm(match);
          }
        } else if (lots.length > 0) {
          applyLotToForm(lots[0]);
        } else if (comms.length > 0) {
          setCommodityId(comms[0].id);
          setCommodityName(comms[0].name);
        }
      } catch (err) {
        console.error('Failed to load initial form data:', err);
      }
    };
    loadInitialData();
  }, [initialLotId]);

  const handleLotSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const lotId = e.target.value;
    setSelectedLotId(lotId);
    if (lotId === 'manual') {
      setSelectedLotId('');
      return;
    }
    const match = myLots.find((l) => l.id === lotId);
    if (match) {
      applyLotToForm(match);
    }
  };

  const handleCommodityChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const id = e.target.value;
    setCommodityId(id);
    const comm = commodities.find((c) => c.id === id);
    if (comm) {
      setCommodityName(comm.name);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (quantityQuintals <= 0) {
      setError('Please specify a positive produce quantity in quintals.');
      return;
    }

    setLoading(true);
    setError(null);
    setRecommendationResult(null);

    try {
      const response = await api.getBuyerRecommendation({
        commodity_id: commodityId || undefined,
        commodity_name: commodityName || undefined,
        quantity_quintals: quantityQuintals,
        quality_grade: qualityGrade || undefined,
        pickup_location_name: pickupLocationName,
        availability_date: availabilityDate,
      });
      setRecommendationResult(response);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to retrieve recommendation';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const bestOption: EconomicOptionBreakdown | undefined = recommendationResult?.recommended_option;

  return (
    <div className="container" style={{ paddingTop: '1.5rem', paddingBottom: '3.5rem' }}>
      {/* Page Header */}
      <div className="page-header-row">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
            <span className="role-pill">DECISION SUPPORT</span>
            <span className="trust-badge-modeled">📊 Market Intelligence Engine</span>
          </div>
          <h1 className="page-title">Best Available Selling Option</h1>
          <p className="page-subtitle">
            Analyze verified buyer requirements, approved market-price intelligence, and modeled transportation deductions to estimate Expected Net Realization.
          </p>
        </div>
        <button className="btn-secondary" onClick={() => onNavigate('farmer-dashboard')}>
          ← Back to Dashboard
        </button>
      </div>

      {/* Main Content Layout: Left Form + Right Advisor / Results */}
      <div className="recommendation-grid">
        
        {/* LEFT PANEL: Produce & Farm Details Form */}
        <div className="card" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--color-text-main)', marginBottom: '0.25rem' }}>
            🌾 Produce & Farm Details
          </h3>
          <p className="subtext" style={{ marginBottom: '1.25rem' }}>
            Configure your harvest volume and location to evaluate economic net realization across buyers.
          </p>

          {myLots.length > 0 && (
            <div className="form-group">
              <label htmlFor="lotSelect" className="form-label">
                Quick Fill from My Listings
              </label>
              <select
                id="lotSelect"
                className="form-select"
                value={selectedLotId || 'manual'}
                onChange={handleLotSelectChange}
              >
                {myLots.map((lot) => (
                  <option key={lot.id} value={lot.id}>
                    {lot.title} ({lot.available_quantity} {lot.unit} of {lot.commodity_name})
                  </option>
                ))}
                <option value="manual">✍ Enter details manually...</option>
              </select>
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div className="form-group">
              <label htmlFor="commoditySelect" className="form-label">
                Target Crop
              </label>
              <select
                id="commoditySelect"
                className="form-select"
                value={commodityId}
                onChange={handleCommodityChange}
                required
              >
                {commodities.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.category.toUpperCase()})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label htmlFor="quantityInput" className="form-label">
                  Quantity (Quintals)
                </label>
                <input
                  id="quantityInput"
                  type="number"
                  step="0.1"
                  min="0.1"
                  className="form-input"
                  value={quantityQuintals}
                  onChange={(e) => setQuantityQuintals(parseFloat(e.target.value) || 0)}
                  required
                />
                <span className="form-helper">1 Quintal = 100 kg</span>
              </div>

              <div className="form-group">
                <label htmlFor="qualitySelect" className="form-label">
                  Quality Grade
                </label>
                <select
                  id="qualitySelect"
                  className="form-select"
                  value={qualityGrade}
                  onChange={(e) => setQualityGrade(e.target.value)}
                >
                  <option value="Standard">Standard (FAQ)</option>
                  <option value="Grade A">Grade A / Premium</option>
                  <option value="Grade B">Grade B / Medium</option>
                  <option value="Grade C">Grade C / Small</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="pickupInput" className="form-label">
                Pickup Location / Farm Gate
              </label>
              <input
                id="pickupInput"
                type="text"
                className="form-input"
                value={pickupLocationName}
                onChange={(e) => setPickupLocationName(e.target.value)}
                placeholder="e.g. Farm Gate, Pune"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="dateInput" className="form-label">
                Produce Ready Date
              </label>
              <input
                id="dateInput"
                type="date"
                className="form-input"
                value={availabilityDate}
                onChange={(e) => setAvailabilityDate(e.target.value)}
                required
              />
            </div>

            {error && (
              <div className="alert-box alert-error" style={{ marginTop: '0.25rem' }}>
                <span>✕</span>
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              className="btn-primary btn-block btn-lg"
              disabled={loading}
              style={{ marginTop: '0.5rem' }}
            >
              {loading ? 'Analyzing Market Options...' : '🚀 Calculate Best Selling Option'}
            </button>
          </form>
        </div>

        {/* RIGHT PANEL: Advisor (Pre-Calculation) OR Results (Post-Calculation) */}
        <div>
          {loading && (
            <div className="card" style={{ padding: '3rem 2rem', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>⏳</div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--color-text-main)', marginBottom: '0.35rem' }}>
                Analyzing Market Realizations...
              </h3>
              <p className="subtext" style={{ maxWidth: '420px', margin: '0 auto' }}>
                Matching verified buyer requirements, computing road route freight deductions, and retrieving ML price forecasts.
              </p>
            </div>
          )}

          {/* INITIAL STATE: Small Contained Advisor Panel */}
          {!loading && !recommendationResult && (
            <div className="card" style={{ padding: '1.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', borderBottom: '1px solid var(--color-border-light)', paddingBottom: '0.75rem' }}>
                <span style={{ fontSize: '1.25rem', lineHeight: 1 }}>🌾</span>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 800, margin: 0, color: 'var(--color-text-main)' }}>
                  AgriMandi Decision Advisor
                </h3>
              </div>

              <div style={{ textAlign: 'center', marginBottom: '1.25rem' }}>
                <img
                  src="/assets/images/clay_farmer_mascot.jpg"
                  alt="AgriMandi Advisor Guide"
                  className="advisor-clay-illustration"
                />
                <h4 style={{ fontSize: '1.05rem', fontWeight: 800, color: 'var(--color-text-main)', marginBottom: '0.35rem' }}>
                  Ready to compare your selling options?
                </h4>
                <p className="subtext" style={{ maxWidth: '440px', margin: '0 auto 1.25rem auto', lineHeight: 1.45 }}>
                  We'll compare active buyer demand, approved Agmarknet price intelligence, and estimated logistics deductions to calculate your highest net profit.
                </p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', background: 'var(--color-surface-muted)', padding: '1rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-border-light)' }}>
                <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-text-main)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.2rem' }}>
                  How It Works:
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: 'var(--text-xs)', color: 'var(--color-text-body)' }}>
                  <span style={{ color: 'var(--color-success)', fontWeight: 800 }}>✓</span>
                  <span><strong>Verified Buyer Demands:</strong> Matching active mill, processor, and trader orders.</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: 'var(--text-xs)', color: 'var(--color-text-body)' }}>
                  <span style={{ color: 'var(--color-info)', fontWeight: 800 }}>~</span>
                  <span><strong>t+1 ML Forecast:</strong> Agmarknet ensemble price prediction with 80% intervals.</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: 'var(--text-xs)', color: 'var(--color-text-body)' }}>
                  <span style={{ color: 'var(--color-warning)', fontWeight: 800 }}>🚛</span>
                  <span><strong>OR-Tools Route Freight:</strong> Accurate road transport cost per quintal.</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: 'var(--text-xs)', color: 'var(--color-text-body)' }}>
                  <span style={{ color: 'var(--color-primary)', fontWeight: 800 }}>₹</span>
                  <span><strong>Net Realization:</strong> True take-home earnings before committing harvest.</span>
                </div>
              </div>
            </div>
          )}

          {/* POST-CALCULATION RESULTS */}
          {!loading && recommendationResult?.status === 'SUCCESS' && bestOption && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Best Option Card */}
              <div className="card" style={{ border: '1px solid var(--color-primary-border)', padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', borderBottom: '1px solid var(--color-border-light)', paddingBottom: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span className="badge-verified">★ RECOMMENDED BUYER</span>
                    {bestOption.is_platform_registered ? (
                      <span className="status-pill status-accepted">✓ Verified Buyer</span>
                    ) : (
                      <span className="price-mode-pill price-mode-fixed">ℹ Directory Listing</span>
                    )}
                  </div>
                  <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-primary)' }}>
                    Match Score: {bestOption.match_score}/100
                  </span>
                </div>

                <div style={{ marginBottom: '1.25rem' }}>
                  <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--color-text-main)', marginBottom: '0.2rem' }}>
                    {bestOption.business_name}
                  </h2>
                  <div className="subtext">
                    📍 Destination: <strong>{bestOption.destination_name}</strong> • Distance: <strong>{bestOption.road_distance_km} km</strong> ({bestOption.buyer_type})
                  </div>
                </div>

                {/* Net Realization Waterfall */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem', background: 'var(--color-surface-muted)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)', padding: '1rem', marginBottom: '1.25rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span className="metric-label">Expected Price</span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text-main)' }}>
                      ₹{bestOption.expected_unit_price} <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-secondary)' }}>/ QTL</span>
                    </span>
                    <span className="subtext">Gross: ₹{bestOption.gross_selling_value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span className="metric-label" style={{ color: 'var(--color-danger)' }}>Transport Estimate</span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-danger)' }}>
                      -₹{bestOption.logistics_deduction.cost_per_quintal} <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-danger)' }}>/ QTL</span>
                    </span>
                    <span className="subtext" style={{ color: 'var(--color-danger)' }}>-₹{bestOption.logistics_deduction.total_transport_cost.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', background: 'var(--color-primary-light)', padding: '0.6rem 0.75rem', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-primary-border)' }}>
                    <span className="metric-label" style={{ color: 'var(--color-primary-dark)' }}>Expected Net</span>
                    <span style={{ fontSize: '1.45rem', fontWeight: 900, color: 'var(--color-primary-dark)' }}>
                      ₹{bestOption.net_realization_per_quintal} <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--color-primary-dark)' }}>/ QTL</span>
                    </span>
                    <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-primary)' }}>
                      Total Net: ₹{bestOption.expected_net_realization.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
                  <button className="btn-primary" onClick={() => onNavigate('requirements')}>
                    View Buyer Demands ➔
                  </button>
                  <button className="btn-secondary" onClick={() => onNavigate('marketplace')}>
                    Marketplace Listings
                  </button>
                </div>

                {/* Forecast Context Card if available */}
                {recommendationResult.forecast_reference.is_forecast_available && (
                  <div className="trust-panel trust-panel-modeled" style={{ marginBottom: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                      <span className="trust-badge-modeled">~ ML PRICE FORECAST</span>
                      <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--color-info)' }}>Next-Day APMC Modal Prediction</strong>
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-info)' }}>
                      Predicted Modal Rate: <strong>₹{recommendationResult.forecast_reference.predicted_price_per_quintal}/qtl</strong>
                      {recommendationResult.forecast_reference.interval_lower_bound && (
                        <span> (80% Confidence Range: ₹{recommendationResult.forecast_reference.interval_lower_bound} – ₹{recommendationResult.forecast_reference.interval_upper_bound})</span>
                      )}
                    </div>
                  </div>
                )}

                {/* Trust & Provenance Breakdown */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem' }}>
                  {bestOption.verified_facts.length > 0 && (
                    <div className="trust-panel trust-panel-verified" style={{ margin: 0, padding: '0.75rem' }}>
                      <div style={{ fontWeight: 800, fontSize: 'var(--text-xs)', color: 'var(--color-success)', marginBottom: '0.25rem' }}>
                        ✓ Verified Facts
                      </div>
                      <ul style={{ listStyle: 'none', fontSize: 'var(--text-xs)', color: 'var(--color-text-body)', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        {bestOption.verified_facts.map((f, i) => (
                          <li key={i}>• {f}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {bestOption.modeled_estimates.length > 0 && (
                    <div className="trust-panel trust-panel-modeled" style={{ margin: 0, padding: '0.75rem' }}>
                      <div style={{ fontWeight: 800, fontSize: 'var(--text-xs)', color: 'var(--color-info)', marginBottom: '0.25rem' }}>
                        ~ Modeled Estimates
                      </div>
                      <ul style={{ listStyle: 'none', fontSize: 'var(--text-xs)', color: 'var(--color-text-body)', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        {bestOption.modeled_estimates.map((m, i) => (
                          <li key={i}>• {m}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {bestOption.uncertainties_and_cautions.length > 0 && (
                    <div className="trust-panel trust-panel-caution" style={{ margin: 0, padding: '0.75rem' }}>
                      <div style={{ fontWeight: 800, fontSize: 'var(--text-xs)', color: 'var(--color-warning)', marginBottom: '0.25rem' }}>
                        ! Cautions & Notes
                      </div>
                      <ul style={{ listStyle: 'none', fontSize: 'var(--text-xs)', color: 'var(--color-text-body)', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        {bestOption.uncertainties_and_cautions.map((c, i) => (
                          <li key={i}>• {c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>

              {/* Alternative Options Table / List */}
              {recommendationResult.alternative_options && recommendationResult.alternative_options.length > 0 && (
                <div className="card" style={{ padding: '1.25rem' }}>
                  <h4 style={{ fontSize: 'var(--text-base)', fontWeight: 800, color: 'var(--color-text-main)', marginBottom: '0.75rem' }}>
                    Alternative Commercial Matches ({recommendationResult.alternative_options.length})
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {recommendationResult.alternative_options.map((alt, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '0.75rem 1rem',
                          background: 'var(--color-surface)',
                          border: '1px solid var(--color-border)',
                          borderRadius: 'var(--radius-xs)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          flexWrap: 'wrap',
                          gap: '0.5rem',
                        }}
                      >
                        <div>
                          <strong style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-main)' }}>{alt.business_name}</strong>
                          <div className="subtext">
                            📍 {alt.destination_name} • {alt.road_distance_km} km • Offer @ ₹{alt.expected_unit_price}/qtl
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', textTransform: 'uppercase' }}>Net Realization</div>
                          <strong style={{ fontSize: '1rem', color: 'var(--color-primary)' }}>
                            ₹{alt.net_realization_per_quintal} / qtl
                          </strong>
                          <div className="subtext">Total: ₹{alt.expected_net_realization.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
