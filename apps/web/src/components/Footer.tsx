import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="footer-container">
      <div className="footer-content">
        <div className="footer-brand">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '1.5rem', lineHeight: 1 }}>🌱</span>
            <strong style={{ fontSize: '1.25rem', color: 'var(--color-primary-dark)', fontWeight: 900 }}>AgriMandi</strong>
          </div>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', lineHeight: 1.5, margin: 0 }}>
            National agricultural trade exchange powering direct farmer market access, multi-farmer harvest aggregation, AI price forecasting, and multi-stop logistics execution.
          </p>
        </div>

        <div>
          <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 800, color: 'var(--color-text-main)', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Core Crops
          </h4>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
            <li>🥦 Fresh Vegetables (Onions, Tomatoes, Potatoes)</li>
            <li>🍎 Premium Fruits (Mangoes, Pomegranates, Grapes)</li>
            <li>🌾 Grains & Cereals (Sharbati Wheat, Basmati)</li>
            <li>🫘 Pulses & Legumes (Chana, Tur/Arhar, Moong)</li>
            <li>🌿 Organic Spices (Turmeric, Jeera, Pepper)</li>
          </ul>
        </div>

        <div>
          <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 800, color: 'var(--color-text-main)', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Technology & Intelligence
          </h4>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
            <li>📊 Agmarknet-Trained Price Forecasting</li>
            <li>🗺️ Leaflet OpenStreetMap Route Planning</li>
            <li>🚛 Google OR-Tools VRP Optimization</li>
            <li>📦 Multi-Farmer Harvest Aggregation Engine</li>
          </ul>
        </div>

        <div style={{ maxWidth: '280px' }}>
          <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 800, color: 'var(--color-text-main)', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            System Architecture
          </h4>
          <div style={{ padding: '0.75rem 1rem', background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: 'var(--text-xs)', fontWeight: 800, color: 'var(--color-primary)', marginBottom: '0.2rem' }}>
              SIH 2026 PS SIH26033
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>
              FastAPI • PostgreSQL / PostGIS • React 19 • Leaflet OSM • OR-Tools
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bottom">
        <div>© {new Date().getFullYear()} AgriMandi. National Agri Trade Exchange. All rights reserved.</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: 'var(--radius-pill)', background: 'var(--color-primary)' }}></span>
          <span style={{ fontWeight: 700, color: 'var(--color-primary)' }}>Phase 2 Verified Logistics & Market Engine</span>
        </div>
      </div>
    </footer>
  );
};

