import React, { useEffect, useState } from 'react';
import { api, type Commodity, type ProduceLotSummary } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface LandingViewProps {
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const LandingView: React.FC<LandingViewProps> = ({ onNavigate }) => {
  const { user, isAuthenticated } = useAuth();
  const [featuredLots, setFeaturedLots] = useState<ProduceLotSummary[]>([]);
  const [, setCommodities] = useState<Commodity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [marketRes, comms] = await Promise.all([
          api.browseMarketplace({ page_size: 6 }),
          api.getCommodities(),
        ]);
        const items = marketRes && Array.isArray(marketRes.items) ? marketRes.items : (Array.isArray(marketRes) ? (marketRes as ProduceLotSummary[]) : []);
        setFeaturedLots(items.slice(0, 6));
        setCommodities(comms);
      } catch (err) {
        console.error('Failed to load landing data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const categories = [
    { key: 'vegetables', label: 'Fresh Vegetables', icon: '🥦', desc: 'Onions, Tomatoes, Potatoes & greens' },
    { key: 'fruits', label: 'Premium Fruits', icon: '🍎', desc: 'Mangoes, Pomegranates, Bananas & grapes' },
    { key: 'grains', label: 'Grains & Cereals', icon: '🌾', desc: 'Sharbati Wheat, Sona Masoori, Basmati' },
    { key: 'pulses', label: 'Pulses & Legumes', icon: '🫘', desc: 'Chana, Tur/Arhar, Moong, Urad' },
    { key: 'spices', label: 'Organic Spices', icon: '🌿', desc: 'Salem Turmeric, Unjha Jeera, Pepper' },
    { key: 'other_crops', label: 'Commercial Crops', icon: '🌻', desc: 'Soybean, Cotton, Groundnut & Mustard' },
  ];

  return (
    <div className="landing-page">
      {/* Hero Section with Liquid Glass & 3D Clay Illustration */}
      <section className="section-container" style={{ paddingTop: '2rem', paddingBottom: '3rem' }}>
        <div
          className="glass-panel landing-hero-grid"
          style={{
            padding: '2.5rem',
            background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.85) 0%, rgba(240, 253, 244, 0.75) 100%)',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: '#dcfce7', color: '#14532d', padding: '0.35rem 0.9rem', borderRadius: '9999px', fontSize: '0.78rem', fontWeight: 800, width: 'fit-content' }}>
              <span>🌾</span>
              <span>SIH26033 • Next-Gen National Agri Trade & Logistics Exchange</span>
            </div>

            <h1 style={{ fontSize: '2.5rem', fontWeight: 900, color: '#0f291e', lineHeight: 1.15, letterSpacing: '-0.02em' }}>
              Direct Farmer Trade.<br />
              <span style={{ color: '#15803d' }}>Transparent Realization.</span><br />
              Verified Logistics.
            </h1>

            <p style={{ fontSize: '1rem', color: '#4d725d', lineHeight: 1.5, maxWidth: '540px' }}>
              Empowering farmers, FPOs, and bulk buyers across India with automated multi-farmer aggregation, AI-driven price intelligence, and verified multi-stop logistics execution.
            </p>

            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
              <button
                className="clay-button-primary"
                onClick={() => onNavigate('marketplace')}
                style={{ fontSize: '1rem', padding: '0.85rem 1.75rem' }}
              >
                Browse Marketplace ➔
              </button>

              {!isAuthenticated ? (
                <button
                  className="btn-secondary"
                  onClick={() => onNavigate('register')}
                  style={{ fontSize: '0.95rem', padding: '0.85rem 1.5rem', fontWeight: 700 }}
                >
                  Register as Producer / Buyer
                </button>
              ) : (
                <button
                  className="btn-secondary"
                  onClick={() => {
                    if (user?.roles.includes('farmer')) onNavigate('farmer-dashboard');
                    else if (user?.roles.includes('fpo')) onNavigate('fpo-dashboard');
                    else if (user?.roles.includes('buyer')) onNavigate('buyer-dashboard');
                    else onNavigate('admin');
                  }}
                  style={{ fontSize: '0.95rem', padding: '0.85rem 1.5rem', fontWeight: 700 }}
                >
                  Go to My Dashboard ➔
                </button>
              )}
            </div>

            {/* Quick Metrics Bar */}
            <div style={{ display: 'flex', gap: '1.5rem', marginTop: '1rem', paddingTop: '1.25rem', borderTop: '1px solid #bbf7d0', flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: '1.3rem', fontWeight: 900, color: '#15803d' }}>737K+</div>
                <div style={{ fontSize: '0.72rem', color: '#4d725d', fontWeight: 600 }}>Agmarknet Price Records</div>
              </div>
              <div>
                <div style={{ fontSize: '1.3rem', fontWeight: 900, color: '#15803d' }}>OR-Tools</div>
                <div style={{ fontSize: '0.72rem', color: '#4d725d', fontWeight: 600 }}>VRP Multi-Stop Routing</div>
              </div>
              <div>
                <div style={{ fontSize: '1.3rem', fontWeight: 900, color: '#15803d' }}>0%</div>
                <div style={{ fontSize: '0.72rem', color: '#4d725d', fontWeight: 600 }}>Middleman Commission</div>
              </div>
            </div>
          </div>

          {/* Hero 3D Clay Illustration */}
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <div
              style={{
                width: '100%',
                maxWidth: '480px',
                borderRadius: '24px',
                overflow: 'hidden',
                boxShadow: '0 20px 40px rgba(21, 128, 61, 0.18)',
                border: '4px solid #ffffff',
              }}
            >
              <img
                src="/assets/images/clay_smart_farm_hero.jpg"
                alt="AgriMandi Smart Farm Operations"
                style={{ width: '100%', height: 'auto', display: 'block', objectFit: 'cover' }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* Categories Grid */}
      <section className="section-container" style={{ paddingTop: '1rem' }}>
        <div style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f291e', marginBottom: '0.25rem' }}>
            Explore Core Crop Categories
          </h2>
          <p style={{ fontSize: '0.875rem', color: '#4d725d' }}>
            Transparent spot market for perishable produce, staple grains, and commercial crops
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1.25rem' }}>
          {categories.map((c) => (
            <div
              key={c.key}
              className="glass-card"
              onClick={() => onNavigate('marketplace', { category: c.key })}
              role="button"
              tabIndex={0}
              style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
            >
              <div style={{ fontSize: '2rem' }}>{c.icon}</div>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f291e' }}>{c.label}</h3>
              <p style={{ fontSize: '0.75rem', color: '#4d725d', flex: 1 }}>{c.desc}</p>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#15803d', marginTop: '0.25rem' }}>
                View listings ➔
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Live Produce Listings Preview */}
      <section className="section-container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f291e', marginBottom: '0.25rem' }}>
              Live Produce Listings
            </h2>
            <p style={{ fontSize: '0.875rem', color: '#4d725d' }}>
              Direct from verified farmers and aggregated FPO mandi yards
            </p>
          </div>
          <button className="btn-secondary" onClick={() => onNavigate('marketplace')}>
            View All ({featuredLots.length > 0 ? `${featuredLots.length}+ Available` : 'Browse'}) ➔
          </button>
        </div>

        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#4d725d' }}>Loading marketplace lots...</div>
        ) : featuredLots.length === 0 ? (
          <div className="glass-panel" style={{ padding: '3rem', textAlign: 'center' }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>📦</div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#0f291e', marginBottom: '0.5rem' }}>No Produce Listed Yet</h3>
            <p style={{ fontSize: '0.875rem', color: '#4d725d', marginBottom: '1.25rem' }}>Be the first farmer or FPO to list your harvested crop on the national exchange.</p>
            {isAuthenticated ? (
              <button className="clay-button-primary" onClick={() => onNavigate('create-lot')}>
                List Your Harvest Now
              </button>
            ) : (
              <button className="clay-button-primary" onClick={() => onNavigate('register', { role: 'farmer' })}>
                Register to List Produce
              </button>
            )}
          </div>
        ) : (
          <div className="produce-grid">
            {featuredLots.map((lot) => (
              <div
                key={lot.id}
                className="produce-card"
                onClick={() => onNavigate('produce-detail', { lotId: lot.id })}
                role="button"
                tabIndex={0}
              >
                <div>
                  <div className="produce-card-header">
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, background: '#dcfce7', color: '#15803d', padding: '2px 8px', borderRadius: '4px', textTransform: 'uppercase' }}>
                      {lot.commodity_category}
                    </span>
                    <span style={{ fontSize: '0.68rem', fontWeight: 700, background: '#eff6ff', color: '#1d4ed8', padding: '2px 6px', borderRadius: '4px', textTransform: 'uppercase' }}>
                      {lot.status}
                    </span>
                  </div>

                  <h3 className="produce-commodity-title">{lot.title}</h3>
                  <div style={{ fontSize: '0.82rem', color: '#4d725d', marginBottom: '0.75rem' }}>{lot.commodity_name}</div>

                  <div className="produce-meta-row">
                    <span style={{ color: '#4d725d' }}>Quantity:</span>
                    <strong>{lot.available_quantity} {lot.unit}</strong>
                  </div>

                  {lot.asking_price_per_unit && (
                    <div className="produce-meta-row">
                      <span style={{ color: '#4d725d' }}>Asking Price:</span>
                      <span className="produce-price-highlight">₹{lot.asking_price_per_unit.toLocaleString('en-IN')}/{lot.unit}</span>
                    </div>
                  )}

                  <div className="produce-meta-row">
                    <span style={{ color: '#4d725d' }}>Location:</span>
                    <span>{lot.pickup_location?.district || lot.pickup_location?.name}, {lot.pickup_location?.state}</span>
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '0.78rem', color: '#4d725d' }}>
                    <strong>{lot.seller_name}</strong> ({lot.seller_role.toUpperCase()})
                  </div>
                  <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#15803d' }}>View Lot ➔</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Stakeholder Architecture Grid */}
      <section className="section-container" style={{ paddingBottom: '4rem' }}>
        <div style={{ marginBottom: '1.5rem' }}>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#0f291e', marginBottom: '0.25rem' }}>
            Built For Every Agri Stakeholder
          </h2>
          <p style={{ fontSize: '0.875rem', color: '#4d725d' }}>
            Tailored workflows designed for India's agricultural supply chain
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
          <div className="clay-card">
            <div style={{ fontSize: '2.25rem', marginBottom: '0.5rem' }}>👨‍🌾</div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0f291e', marginBottom: '0.5rem' }}>For Farmers</h3>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem', color: '#4d725d', marginBottom: '1.25rem' }}>
              <li>✓ Post produce listings with asking price and pickup location</li>
              <li>✓ AI Decision Engine computes Expected Net Realization</li>
              <li>✓ Accept or reject commercial offers with instant order confirmation</li>
              <li>✓ Verified pickup routing without exploitation</li>
            </ul>
            <button className="btn-secondary" onClick={() => onNavigate('register', { role: 'farmer' })}>
              Join as Farmer
            </button>
          </div>

          <div className="clay-card">
            <div style={{ fontSize: '2.25rem', marginBottom: '0.5rem' }}>🏢</div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0f291e', marginBottom: '0.5rem' }}>For FPOs & Cooperatives</h3>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem', color: '#4d725d', marginBottom: '1.25rem' }}>
              <li>✓ Aggregate member lots into high-volume commercial batches</li>
              <li>✓ Track individual farmer contributions transparently</li>
              <li>✓ Fulfill bulk institutional buyer requirements at premium rates</li>
              <li>✓ Official legal registration verification and mandi badges</li>
            </ul>
            <button className="btn-secondary" onClick={() => onNavigate('register', { role: 'fpo' })}>
              Join as FPO
            </button>
          </div>

          <div className="clay-card">
            <div style={{ fontSize: '2.25rem', marginBottom: '0.5rem' }}>🏭</div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: '#0f291e', marginBottom: '0.5rem' }}>For Buyers & Processors</h3>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem', color: '#4d725d', marginBottom: '1.25rem' }}>
              <li>✓ Browse farm-gate produce across 6 core categories</li>
              <li>✓ Post procurement requirements and automated supply matching</li>
              <li>✓ Multi-farmer aggregation shipment planning and tracking</li>
              <li>✓ Structured invoice generation and milestone fulfilment</li>
            </ul>
            <button className="btn-secondary" onClick={() => onNavigate('register', { role: 'buyer' })}>
              Join as Buyer
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};
