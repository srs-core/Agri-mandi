import React, { useState } from 'react';

interface DesignSystemShowcaseViewProps {
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const DesignSystemShowcaseView: React.FC<DesignSystemShowcaseViewProps> = ({ onNavigate }) => {
  const [activeTab, setActiveTab] = useState<'tokens' | 'buttons' | 'forms' | 'cards' | 'tables' | 'badges' | 'trust' | 'modals' | 'states'>('tokens');
  const [showModal, setShowModal] = useState(false);
  const [sampleInput, setSampleInput] = useState('Sharbati Wheat Grade-A');
  const [sampleSelect, setSampleSelect] = useState('QTL');

  return (
    <div className="section-container">
      {/* Page Header */}
      <div className="page-header-row">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
            <span className="role-pill">DESIGN SYSTEM SHELL</span>
            <span className="badge-verified">✓ APPROVED SPEC</span>
          </div>
          <h1 className="page-title">AgriMandi Design System & Application Shell</h1>
          <p className="page-subtitle">
            Coherent, trusted, professional Indian agricultural trading and logistics platform visual language.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn-secondary" onClick={() => onNavigate('marketplace')}>
            ← Back to Marketplace
          </button>
          <button className="btn-primary" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            Top
          </button>
        </div>
      </div>

      {/* Showcase Tabs */}
      <div className="tabs-header-row">
        <div className="tab-buttons">
          <button
            className={`tab-btn ${activeTab === 'tokens' ? 'active' : ''}`}
            onClick={() => setActiveTab('tokens')}
          >
            🎨 Tokens & Geometry
          </button>
          <button
            className={`tab-btn ${activeTab === 'buttons' ? 'active' : ''}`}
            onClick={() => setActiveTab('buttons')}
          >
            🔘 Buttons
          </button>
          <button
            className={`tab-btn ${activeTab === 'forms' ? 'active' : ''}`}
            onClick={() => setActiveTab('forms')}
          >
            📝 Forms & Inputs
          </button>
          <button
            className={`tab-btn ${activeTab === 'cards' ? 'active' : ''}`}
            onClick={() => setActiveTab('cards')}
          >
            🗂️ Cards & Metrics
          </button>
          <button
            className={`tab-btn ${activeTab === 'tables' ? 'active' : ''}`}
            onClick={() => setActiveTab('tables')}
          >
            📊 Tables
          </button>
          <button
            className={`tab-btn ${activeTab === 'badges' ? 'active' : ''}`}
            onClick={() => setActiveTab('badges')}
          >
            🏷️ Badges & Status
          </button>
          <button
            className={`tab-btn ${activeTab === 'trust' ? 'active' : ''}`}
            onClick={() => setActiveTab('trust')}
          >
            🛡️ Trust UI
          </button>
          <button
            className={`tab-btn ${activeTab === 'modals' ? 'active' : ''}`}
            onClick={() => setActiveTab('modals')}
          >
            🪟 Modals & Alerts
          </button>
          <button
            className={`tab-btn ${activeTab === 'states' ? 'active' : ''}`}
            onClick={() => setActiveTab('states')}
          >
            ⏳ Skeletons & Empty
          </button>
        </div>
      </div>

      {/* TAB 1: TOKENS & GEOMETRY */}
      {activeTab === 'tokens' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="card">
            <h3>Brand Palette & Design Tokens</h3>
            <p className="subtext" style={{ marginBottom: '1rem' }}>
              Consolidated color tokens prioritizing trust, readability, and agricultural context.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
              <div style={{ padding: '1rem', background: 'var(--color-primary)', color: '#fff', borderRadius: 'var(--radius-sm)' }}>
                <strong>Primary Green</strong>
                <div style={{ fontSize: '0.8rem', opacity: 0.9 }}>#138A43</div>
                <div style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}>--color-primary</div>
              </div>

              <div style={{ padding: '1rem', background: 'var(--color-primary-dark)', color: '#fff', borderRadius: 'var(--radius-sm)' }}>
                <strong>Primary Dark</strong>
                <div style={{ fontSize: '0.8rem', opacity: 0.9 }}>#094522</div>
                <div style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}>--color-primary-dark</div>
              </div>

              <div style={{ padding: '1rem', background: 'var(--color-primary-light)', color: 'var(--color-primary-dark)', border: '1px solid var(--color-primary-border)', borderRadius: 'var(--radius-sm)' }}>
                <strong>Primary Light</strong>
                <div style={{ fontSize: '0.8rem' }}>#EAF6EE</div>
                <div style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}>--color-primary-light</div>
              </div>

              <div style={{ padding: '1rem', background: 'var(--color-accent)', color: '#fff', borderRadius: 'var(--radius-sm)' }}>
                <strong>Commodity Amber</strong>
                <div style={{ fontSize: '0.8rem', opacity: 0.9 }}>#C27803</div>
                <div style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}>--color-accent</div>
              </div>

              <div style={{ padding: '1rem', background: 'var(--color-background)', color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)' }}>
                <strong>Canvas Background</strong>
                <div style={{ fontSize: '0.8rem' }}>#F4F8F1</div>
                <div style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}>--color-background</div>
              </div>

              <div style={{ padding: '1rem', background: 'var(--color-surface)', color: 'var(--color-text)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-sm)' }}>
                <strong>Card Surface</strong>
                <div style={{ fontSize: '0.8rem' }}>#FFFFFF</div>
                <div style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}>--color-surface</div>
              </div>
            </div>
          </div>

          <div className="card">
            <h3>Geometry System (Sharp / 2–4px Radius)</h3>
            <p className="subtext" style={{ marginBottom: '1rem' }}>
              Strictly low-radius geometry. No 16px/20px bubbly containers or excessive glass halos.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
              <div style={{ padding: '1rem', background: '#fff', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xs)' }}>
                <strong>Radius XS / SM: 2px</strong>
                <p className="subtext" style={{ margin: '0.25rem 0 0 0' }}>Form inputs, standard buttons, tabs, tags.</p>
              </div>
              <div style={{ padding: '1rem', background: '#fff', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)' }}>
                <strong>Radius MD / LG: 4px</strong>
                <p className="subtext" style={{ margin: '0.25rem 0 0 0' }}>Cards, panels, modal dialogs, tables.</p>
              </div>
              <div style={{ padding: '1rem', background: '#fff', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-pill)' }}>
                <strong>Radius Pill: 9999px</strong>
                <p className="subtext" style={{ margin: '0.25rem 0 0 0' }}>Compact badges, status tags, count pills only.</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: BUTTON SYSTEM */}
      {activeTab === 'buttons' && (
        <div className="card">
          <h3>Standardized Button Hierarchy</h3>
          <p className="subtext" style={{ marginBottom: '1.25rem' }}>
            Unified height (38px standard, 30px compact), font weight, and sharp 2–4px geometry across all variants.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div>
              <h4 style={{ marginBottom: '0.75rem', fontSize: 'var(--text-base)' }}>Standard Actions (38px height)</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
                <button className="btn-primary">Primary Action</button>
                <button className="btn-secondary">Secondary Action</button>
                <button className="btn-outline">Outline Action</button>
                <button className="btn-success">Accept / Confirm</button>
                <button className="btn-counter-sm" style={{ minHeight: '38px', padding: '0.5rem 1rem' }}>💬 Counter Offer</button>
                <button className="btn-danger">Decline / Reject</button>
                <button className="btn-ghost">Ghost Action</button>
                <button className="btn-link">Text Link Action</button>
              </div>
            </div>

            <div>
              <h4 style={{ marginBottom: '0.75rem', fontSize: 'var(--text-base)' }}>Compact Actions (30px height)</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                <button className="btn-success-sm">✓ Accept ₹1,700</button>
                <button className="btn-counter-sm">💬 Counter</button>
                <button className="btn-danger-sm">✕ Decline</button>
                <button className="btn-secondary btn-sm">Details</button>
                <button className="btn-outline btn-sm">Edit Lot</button>
              </div>
            </div>

            <div>
              <h4 style={{ marginBottom: '0.75rem', fontSize: 'var(--text-base)' }}>Interactive & Disabled States</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
                <button className="btn-primary" disabled>Primary (Disabled)</button>
                <button className="btn-secondary" disabled>Secondary (Disabled)</button>
                <button className="btn-primary">
                  <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>⏳</span> Processing...
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: FORM SYSTEM */}
      {activeTab === 'forms' && (
        <div className="card">
          <h3>Standardized Form Controls</h3>
          <p className="subtext" style={{ marginBottom: '1.25rem' }}>
            Sharp rectangular inputs, strong labels, clear focus states, helper text, and validation feedback.
          </p>

          <form onSubmit={(e) => e.preventDefault()} style={{ maxWidth: '680px' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="sample-title">
                Produce Listing Title <span style={{ color: 'var(--color-danger)' }}>*</span>
              </label>
              <input
                id="sample-title"
                type="text"
                className="form-input"
                value={sampleInput}
                onChange={(e) => setSampleInput(e.target.value)}
                placeholder="e.g. Nashik Red Onions"
              />
              <span className="form-helper">Enter a descriptive title with grade, variety, and harvest condition.</span>
            </div>

            <div className="form-grid-2">
              <div className="form-group">
                <label className="form-label" htmlFor="sample-unit">Quantity Unit</label>
                <select
                  id="sample-unit"
                  className="form-select"
                  value={sampleSelect}
                  onChange={(e) => setSampleSelect(e.target.value)}
                >
                  <option value="QTL">Quintals (QTL)</option>
                  <option value="MT">Metric Tonnes (MT)</option>
                  <option value="KG">Kilograms (KG)</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="sample-price">Price Mode</label>
                <select id="sample-price" className="form-select">
                  <option value="negotiable">Negotiable (Open for Bids)</option>
                  <option value="fixed">Fixed Asking Price</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="sample-notes">Quality & Harvest Notes</label>
              <textarea
                id="sample-notes"
                className="form-textarea"
                placeholder="Moisture level below 12%, sorted and packed in 50kg jute bags..."
                defaultValue="Harvested on August 28, 2026. Grade-A quality, clean sorted."
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="sample-error-input">Invalid Input Demo</label>
              <input
                id="sample-error-input"
                type="text"
                className="form-input"
                defaultValue="-50 QTL"
                style={{ borderColor: 'var(--color-danger)' }}
              />
              <span className="form-error">Quantity must be a positive number greater than 0.</span>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
              <button type="button" className="btn-primary">Save Changes</button>
              <button type="button" className="btn-secondary">Reset</button>
            </div>
          </form>
        </div>
      )}

      {/* TAB 4: CARDS & METRIC PANELS */}
      {activeTab === 'cards' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div>
            <h3 style={{ marginBottom: '1rem' }}>High-Impact Operational KPI Grid</h3>
            <div className="kpi-grid">
              <div className="metric-card">
                <span className="metric-label">Active Marketplace Lots</span>
                <span className="metric-value">48</span>
                <span className="metric-sub">Across 12 APMC Mandis</span>
              </div>

              <div className="metric-card">
                <span className="metric-label">Live In-Transit Cargo</span>
                <span className="metric-value">185 QTL</span>
                <span className="metric-sub">4 active multi-stop routes</span>
              </div>

              <div className="metric-card">
                <span className="metric-label">Agreed Gross Trade Value</span>
                <span className="metric-value price-text">₹4,28,500</span>
                <span className="metric-sub">100% verified settlement</span>
              </div>

              <div className="metric-card">
                <span className="metric-label">Transport Capacity</span>
                <span className="metric-value">92%</span>
                <span className="metric-sub">Optimal VRP load factor</span>
              </div>
            </div>
          </div>

          <div className="ai-decision-banner">
            <div className="ai-banner-left">
              <div className="ai-banner-icon">🤖</div>
              <div>
                <div className="ai-banner-title">Agmarknet AI Price Forecast & Net Realization Engine</div>
                <p className="ai-banner-desc">
                  Calculates optimal destination APMC mandis, estimated transport deductions, and projected net realization with full provenance transparency.
                </p>
              </div>
            </div>
            <button className="btn-secondary" style={{ color: 'var(--color-primary-dark)', fontWeight: 700 }}>
              View Intelligence ➔
            </button>
          </div>
        </div>
      )}

      {/* TAB 5: TABLES */}
      {activeTab === 'tables' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--color-border)' }}>
            <h3 style={{ margin: 0 }}>Active Commercial Offers Table</h3>
          </div>
          <div className="table-container" style={{ margin: 0, border: 'none' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Produce & Commodity</th>
                  <th>Quantity</th>
                  <th>Offered Rate</th>
                  <th>Total Value</th>
                  <th>Price Mode</th>
                  <th>Status & Turn</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <div className="lot-name-link">Nashik Red Onions (Lot #481)</div>
                    <div className="subtext">Seller: Ramesh Patil (Farmer)</div>
                  </td>
                  <td>100 QTL</td>
                  <td className="price-text">₹800 / QTL</td>
                  <td className="deal-total-text">₹80,000</td>
                  <td><span className="price-mode-pill price-mode-negotiable">Negotiable</span></td>
                  <td>
                    <span className="status-pill status-pending">PENDING</span>
                    <div><span className="turn-badge turn-action-required">⚡ Your Response Required</span></div>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '0.4rem' }}>
                      <button className="btn-success-sm">✓ Accept</button>
                      <button className="btn-counter-sm">💬 Counter</button>
                      <button className="btn-danger-sm">✕ Decline</button>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td>
                    <div className="lot-name-link">Jyoti Potatoes Grade-A (Lot #412)</div>
                    <div className="subtext">Buyer: FreshFoods Supply Chain</div>
                  </td>
                  <td>30 QTL</td>
                  <td className="price-text">₹1,700 / QTL</td>
                  <td className="deal-total-text">₹51,000</td>
                  <td><span className="price-mode-pill price-mode-fixed">Fixed Price</span></td>
                  <td>
                    <span className="status-pill status-accepted">ACCEPTED</span>
                    <div><span className="turn-badge turn-waiting">Order #db650013</span></div>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn-secondary btn-sm">View Order ➔</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 6: BADGES & STATUS */}
      {activeTab === 'badges' && (
        <div className="card">
          <h3>Status, Role & Provenance Badges</h3>
          <p className="subtext" style={{ marginBottom: '1.25rem' }}>
            Semantic badges adhering to accessible color contrasts and sharp pill/tag geometry.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div>
              <h4 style={{ fontSize: 'var(--text-base)', marginBottom: '0.5rem' }}>Workflow & Order Statuses</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                <span className="status-pill status-pending">PENDING</span>
                <span className="status-pill status-countered">COUNTERED</span>
                <span className="status-pill status-accepted">ACCEPTED</span>
                <span className="status-pill status-declined">DECLINED</span>
                <span className="status-pill status-in_transit">IN TRANSIT</span>
                <span className="status-pill status-completed">DELIVERED</span>
                <span className="status-pill status-sold">SOLD</span>
              </div>
            </div>

            <div>
              <h4 style={{ fontSize: 'var(--text-base)', marginBottom: '0.5rem' }}>Price Modes & Turns</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                <span className="price-mode-pill price-mode-negotiable">⚡ NEGOTIABLE</span>
                <span className="price-mode-pill price-mode-fixed">🔒 FIXED PRICE</span>
                <span className="turn-badge turn-action-required">⚡ Your Response Required</span>
                <span className="turn-badge turn-waiting">⏳ Awaiting Counterparty Response</span>
              </div>
            </div>

            <div>
              <h4 style={{ fontSize: 'var(--text-base)', marginBottom: '0.5rem' }}>Role Indicator Pills</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                <span className="role-pill">FARMER</span>
                <span className="role-pill">FPO</span>
                <span className="role-pill">BUYER</span>
                <span className="role-pill">TRANSPORTER</span>
                <span className="role-pill">ADMIN</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 7: TRUST UI SYSTEM */}
      {activeTab === 'trust' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="card">
            <h3>Trust UI & Data Provenance System</h3>
            <p className="subtext" style={{ marginBottom: '1rem' }}>
              Explicitly communicate verified facts, modeled AI estimates, and operational caveats without hiding uncertainty.
            </p>

            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
              <span className="trust-badge-verified">✓ VERIFIED FACT</span>
              <span className="trust-badge-modeled">~ MODELED ESTIMATE</span>
              <span className="trust-badge-caution">! UNVERIFIED / CAUTION</span>
            </div>

            <div className="trust-panel trust-panel-verified">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <span className="trust-badge-verified">✓ VERIFIED APMC DATA</span>
                <strong>Agmarknet Daily Modal Rate</strong>
              </div>
              <p style={{ margin: 0, fontSize: 'var(--text-sm)' }}>
                Official APMC modal price recorded at Azadpur Mandi on August 30, 2026: ₹1,850/QTL.
              </p>
            </div>

            <div className="trust-panel trust-panel-modeled">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <span className="trust-badge-modeled">~ ML PRICE FORECAST</span>
                <strong>Projected Price Realization (95% Confidence)</strong>
              </div>
              <p style={{ margin: 0, fontSize: 'var(--text-sm)' }}>
                RandomForest & LightGBM ensemble predicts price range ₹1,780 – ₹1,920/QTL over next 7 days based on seasonal arrivals and fuel indices.
              </p>
            </div>

            <div className="trust-panel trust-panel-caution">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <span className="trust-badge-caution">! LOGISTICS CAUTION</span>
                <strong>Road Elevation & Monsoon Traffic Delay</strong>
              </div>
              <p style={{ margin: 0, fontSize: 'var(--text-sm)' }}>
                Western Ghats transit route may experience 2–3 hour weather delay. Ensure perishable produce is packed with moisture barrier.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* TAB 8: MODALS & ALERTS */}
      {activeTab === 'modals' && (
        <div className="card">
          <h3>Standardized Modals & Alert Feedback</h3>
          <p className="subtext" style={{ marginBottom: '1.25rem' }}>
            Clean backdrops, accessible dialogs, and clear actionable alert banners.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
            <div className="alert-box alert-success">
              <span>✓</span>
              <span><strong>Success:</strong> Commercial offer accepted! Order #db650013 confirmed and assigned to transport engine.</span>
            </div>

            <div className="alert-box alert-warning">
              <span>⚠️</span>
              <span><strong>Warning:</strong> Produce lot has 10 QTL remaining out of 100 QTL available.</span>
            </div>

            <div className="alert-box alert-error">
              <span>✕</span>
              <span><strong>Error:</strong> Turn violation — you cannot submit a counter-offer on your own proposal.</span>
            </div>

            <div className="alert-box alert-info">
              <span>ℹ️</span>
              <span><strong>Information:</strong> New transport opportunity created for Nashik to Mumbai aggregation route.</span>
            </div>
          </div>

          <button className="btn-primary" onClick={() => setShowModal(true)}>
            Open Standard Modal Preview
          </button>

          {showModal && (
            <div className="modal-overlay" onClick={() => setShowModal(false)}>
              <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                  <h3>Submit Counter Offer</h3>
                  <button className="close-modal-btn" onClick={() => setShowModal(false)}>✕</button>
                </div>
                <div className="modal-body">
                  <div className="form-group">
                    <label className="form-label">Counter Rate (₹ / QTL)</label>
                    <input type="number" className="form-input" defaultValue={1750} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Proposed Quantity (QTL)</label>
                    <input type="number" className="form-input" defaultValue={30} />
                  </div>
                  <div className="alert-box alert-info" style={{ marginTop: '1rem' }}>
                    Calculated Total Value: <strong>₹52,500</strong>
                  </div>
                </div>
                <div className="modal-footer">
                  <button className="btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                  <button className="btn-primary" onClick={() => setShowModal(false)}>Submit Counter Offer</button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 9: SKELETONS & EMPTY STATES */}
      {activeTab === 'states' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="card">
            <h3>Standardized Skeleton Placeholders</h3>
            <p className="subtext" style={{ marginBottom: '1rem' }}>
              Avoid jarring blank screens with smooth pulsing placeholder skeletons.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxWidth: '500px' }}>
              <div className="skeleton-box" style={{ height: '24px', width: '60%' }}></div>
              <div className="skeleton-box" style={{ height: '16px', width: '90%' }}></div>
              <div className="skeleton-box" style={{ height: '16px', width: '75%' }}></div>
              <div className="skeleton-box" style={{ height: '38px', width: '120px', marginTop: '0.5rem' }}></div>
            </div>
          </div>

          <div className="empty-state">
            <div className="empty-state-icon">🌾</div>
            <h3 className="empty-state-title">No Active Commercial Offers</h3>
            <p className="empty-state-desc">
              You currently do not have any pending offers on this produce lot. As soon as a verified buyer places a bid, it will appear here for bilateral review.
            </p>
            <button className="btn-primary" onClick={() => onNavigate('marketplace')}>
              Explore Marketplace Demands
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
