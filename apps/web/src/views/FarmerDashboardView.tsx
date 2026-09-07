import React, { useEffect, useState } from 'react';
import { api, type Offer, type Order, type ProduceLotSummary } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface FarmerDashboardViewProps {
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const FarmerDashboardView: React.FC<FarmerDashboardViewProps> = ({ onNavigate }) => {
  const { user, profile } = useAuth();
  const [myLots, setMyLots] = useState<ProduceLotSummary[]>([]);
  const [incomingOffers, setIncomingOffers] = useState<Offer[]>([]);
  const [myOrders, setMyOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const [lots, offers, orders] = await Promise.all([
          api.getMyProduceLots(),
          api.getOffers({ role_perspective: 'received', status: 'pending' }),
          api.getOrders(),
        ]);
        setMyLots(lots);
        setIncomingOffers(offers);
        setMyOrders(orders);
      } catch (err) {
        console.error('Failed to load farmer dashboard:', err);
      } finally {
        setLoading(false);
      }
    };
    loadDashboard();
  }, []);

  const totalOrdersAmount = myOrders
    .filter((o) => o.status !== 'cancelled')
    .reduce((acc, o) => acc + o.total_amount, 0);

  const publishedLots = myLots.filter((l) => l.status === 'published');

  return (
    <div className="container" style={{ paddingTop: '2rem', paddingBottom: '4rem' }}>
      {/* Farmer Hub Content with subtle translucent watermark background */}
      <div className="farmer-hub-content">
        {/* Contextual Greeting & Farm Actions Card */}
        <div className="dashboard-welcome-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
            <span className="role-pill">FARMER HUB</span>
            {profile?.verification_status === 'verified' && (
              <span className="trust-badge-verified">✓ Verified Producer</span>
            )}
          </div>
          <h1 className="welcome-title">Namaste, {user?.display_name}!</h1>
          <p className="welcome-sub" style={{ marginBottom: '1.25rem' }}>
            Farm: <strong>{profile?.farm_name || 'Family Farm'}</strong> • Mandi Catchment:{' '}
            <strong>{profile?.primary_location ? `${profile.primary_location.district}, ${profile.primary_location.state}` : 'Pune, Maharashtra'}</strong>
          </p>

          <div className="welcome-actions" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="clay-button-primary" onClick={() => onNavigate('recommendation')}>
              <span>🎯</span> Best Selling Option
            </button>
            <button className="btn-secondary" onClick={() => onNavigate('create-lot')}>
              + List New Produce
            </button>
            <button className="btn-secondary" onClick={() => onNavigate('logistics-route')}>
              🚛 Route Map
            </button>
          </div>
        </div>

      {/* 2. Top-Priority KPI Metrics */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Active Produce Lots</span>
          <span className="kpi-value">{publishedLots.length}</span>
          <span className="kpi-sub">Total {myLots.length} listings in mandi</span>
        </div>

        <div className={`kpi-card ${incomingOffers.length > 0 ? 'highlight-card' : ''}`}>
          <span className="kpi-label">Pending Buyer Offers</span>
          <span className="kpi-value" style={{ color: incomingOffers.length > 0 ? '#b45309' : undefined }}>
            {incomingOffers.length}
          </span>
          <span className="kpi-sub">{incomingOffers.length > 0 ? '⚡ Requires your decision' : 'No pending offers'}</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Confirmed Orders</span>
          <span className="kpi-value">{myOrders.filter((o) => o.status !== 'cancelled').length}</span>
          <span className="kpi-sub">Commercial delivery trades</span>
        </div>

        <div className="kpi-card primary-highlight">
          <span className="kpi-label">Realized Revenue</span>
          <span className="kpi-value price-text">
            ₹{totalOrdersAmount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
          </span>
          <span className="kpi-sub">Direct bank settlements</span>
        </div>
      </div>

      {/* 3. AI Decision Engine Banner (Best Selling Option) */}
      <div className="ai-decision-banner">
        <div className="ai-banner-left">
          <div className="ai-banner-icon">💡</div>
          <div>
            <h3 className="ai-banner-title">Maximize Net Realization with AI Decision Support</h3>
            <p className="ai-banner-desc">
              Our ML model compares real verified buyer demands, t+1 Agmarknet forecasts, and transport distance to determine your highest expected net profit per quintal.
            </p>
          </div>
        </div>
        <button
          className="btn-primary"
          style={{ background: '#ffffff', color: '#15803d', border: 'none', fontWeight: 800, fontSize: '0.9rem' }}
          onClick={() => onNavigate('recommendation')}
        >
          Run Recommendation ➔
        </button>
      </div>

      {/* 4. Main Two-Column Layout */}
      <div className="dashboard-grid-layout">
        {/* Left Column: Active Produce Listings */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0f291e' }}>My Harvested Produce Lots</h3>
            <button className="btn-secondary" onClick={() => onNavigate('create-lot')} style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}>
              + Add Produce
            </button>
          </div>

          {loading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: '#4d725d' }}>Loading listings...</div>
          ) : myLots.length === 0 ? (
            <div className="glass-panel" style={{ padding: '2.5rem', textAlign: 'center' }}>
              <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>🌱</div>
              <h4 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#0f291e', marginBottom: '0.4rem' }}>No Produce Listed Yet</h4>
              <p style={{ fontSize: '0.85rem', color: '#4d725d', marginBottom: '1rem' }}>
                List your onions, potatoes, tomatoes, or grains to receive commercial buyer bids.
              </p>
              <button className="clay-button-primary" onClick={() => onNavigate('create-lot')}>
                List First Produce Lot
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {myLots.map((lot) => (
                <div key={lot.id} className="clay-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', padding: '1.25rem 1.5rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                      <span style={{ fontSize: '0.7rem', fontWeight: 700, background: '#dcfce7', color: '#15803d', padding: '2px 8px', borderRadius: '4px', textTransform: 'uppercase' }}>
                        {lot.commodity_category}
                      </span>
                      <span style={{ fontSize: '0.7rem', fontWeight: 700, background: '#eff6ff', color: '#1d4ed8', padding: '2px 6px', borderRadius: '4px', textTransform: 'uppercase' }}>
                        {lot.status}
                      </span>
                      {lot.quality_grade && (
                        <span style={{ fontSize: '0.7rem', fontWeight: 600, color: '#64748b' }}>
                          Grade: {lot.quality_grade}
                        </span>
                      )}
                    </div>

                    <h4 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0f291e', margin: '0 0 0.2rem 0' }}>
                      {lot.title}
                    </h4>
                    <div style={{ fontSize: '0.82rem', color: '#4d725d' }}>
                      Available: <strong>{lot.available_quantity} {lot.unit}</strong> • Pickup: <strong>{lot.pickup_location?.district || lot.pickup_location?.name || 'Local'}</strong>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '0.7rem', color: '#4d725d', textTransform: 'uppercase', fontWeight: 700 }}>
                        {lot.asking_price_per_unit ? 'Asking Price' : 'Price Mode'}
                      </div>
                      <div style={{ fontSize: '1.15rem', fontWeight: 800, color: lot.asking_price_per_unit ? '#15803d' : '#d97706' }}>
                        {lot.asking_price_per_unit
                          ? `₹${lot.asking_price_per_unit.toLocaleString('en-IN')}/${lot.unit}`
                          : '🤝 Negotiable'}
                      </div>
                    </div>
                    <button
                      className="btn-secondary"
                      onClick={() => onNavigate('recommendation', { lotId: lot.id })}
                      style={{ fontSize: '0.82rem', padding: '0.5rem 0.9rem' }}
                    >
                      Best Buyer ➔
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Pending Offers & Operational Insights */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Pending Offers Review */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h4 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0f291e', margin: 0 }}>
                Incoming Offers ({incomingOffers.length})
              </h4>
              <button className="btn-secondary" onClick={() => onNavigate('offers')} style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}>
                View All
              </button>
            </div>

            {incomingOffers.length === 0 ? (
              <p style={{ fontSize: '0.82rem', color: '#4d725d', margin: 0 }}>
                No pending buyer offers. When buyers submit purchase proposals, they will appear here for instant acceptance.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {incomingOffers.slice(0, 3).map((offer) => (
                  <div key={offer.id} style={{ padding: '0.9rem', background: '#ffffff', border: '1px solid #fde68a', borderRadius: '8px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                      <strong style={{ fontSize: '0.875rem', color: '#0f291e' }}>{offer.buyer_name}</strong>
                      <span style={{ fontSize: '0.9rem', fontWeight: 900, color: '#15803d' }}>
                        ₹{offer.offered_price_per_unit}/{offer.unit}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#4d725d', marginBottom: '0.6rem' }}>
                      Offered for <strong>{offer.offered_quantity} {offer.unit}</strong>
                    </div>
                    <button
                      className="clay-button-primary"
                      onClick={() => onNavigate('offers', { lotId: offer.produce_lot_id })}
                      style={{ fontSize: '0.78rem', padding: '0.4rem 0.8rem', width: '100%' }}
                    >
                      Review & Accept ➔
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quick Logistics Route Link */}
          <div className="glass-panel" style={{ padding: '1.5rem', background: 'linear-gradient(135deg, rgba(239, 246, 255, 0.8) 0%, rgba(255, 255, 255, 0.9) 100%)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '1.5rem' }}>🗺️</span>
              <h4 style={{ fontSize: '1.05rem', fontWeight: 800, color: '#1e3a8a', margin: 0 }}>
                Logistics Route Tracking
              </h4>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#4d725d', marginBottom: '1rem', lineHeight: 1.4 }}>
              Inspect multi-stop pickup routes, Google OR-Tools optimization savings, and vehicle payload allocations.
            </p>
            <button
              className="btn-primary"
              onClick={() => onNavigate('logistics-route')}
              style={{ width: '100%', fontSize: '0.85rem' }}
            >
              Open Route Map Explorer ➔
            </button>
          </div>
        </div>
      </div>
      </div>
    </div>
  );
};
