import React, { useEffect, useState } from 'react';
import { api, type BuyerRequirement, type Commodity } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface BuyerRequirementsViewProps {
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const BuyerRequirementsView: React.FC<BuyerRequirementsViewProps> = ({ onNavigate }) => {
  const { user, isAuthenticated } = useAuth();
  const [requirements, setRequirements] = useState<BuyerRequirement[]>([]);
  const [, setCommodities] = useState<Commodity[]>([]);
  const [category, setCategory] = useState<string>('');
  const [commodityId, setCommodityId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [reqs, comms] = await Promise.all([
          api.browseBuyerRequirements({
            category: category || undefined,
            commodity_id: commodityId || undefined,
          }),
          api.getCommodities(),
        ]);
        setRequirements(reqs);
        setCommodities(comms);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load buyer requirements.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [category, commodityId]);

  const isBuyer = user?.roles.includes('buyer');

  return (
    <div className="requirements-page section-container">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Institutional Buyer Demands</h1>
          <p className="page-subtitle">
            Direct procurement requests posted by bulk buyers, food processing mills, and retail aggregators.
          </p>
        </div>
        {isAuthenticated && isBuyer && (
          <button className="btn-primary" onClick={() => onNavigate('create-requirement')}>
            + Post Procurement Requirement
          </button>
        )}
      </div>

      {/* Category Filter */}
      <div className="category-pills-row">
        <button
          className={`pill-btn ${category === '' ? 'active' : ''}`}
          onClick={() => {
            setCategory('');
            setCommodityId('');
          }}
        >
          All Demands
        </button>
        <button
          className={`pill-btn ${category === 'vegetables' ? 'active' : ''}`}
          onClick={() => {
            setCategory('vegetables');
            setCommodityId('');
          }}
        >
          🥦 Vegetables
        </button>
        <button
          className={`pill-btn ${category === 'fruits' ? 'active' : ''}`}
          onClick={() => {
            setCategory('fruits');
            setCommodityId('');
          }}
        >
          🍎 Fruits
        </button>
        <button
          className={`pill-btn ${category === 'grains' ? 'active' : ''}`}
          onClick={() => {
            setCategory('grains');
            setCommodityId('');
          }}
        >
          🌾 Grains
        </button>
        <button
          className={`pill-btn ${category === 'pulses' ? 'active' : ''}`}
          onClick={() => {
            setCategory('pulses');
            setCommodityId('');
          }}
        >
          🫘 Pulses
        </button>
        <button
          className={`pill-btn ${category === 'spices' ? 'active' : ''}`}
          onClick={() => {
            setCategory('spices');
            setCommodityId('');
          }}
        >
          🌿 Spices
        </button>
        <button
          className={`pill-btn ${category === 'other_crops' ? 'active' : ''}`}
          onClick={() => {
            setCategory('other_crops');
            setCommodityId('');
          }}
        >
          🌻 Commercial
        </button>
      </div>

      {error && <div className="alert-box alert-error">{error}</div>}

      {loading ? (
        <div className="loading-spinner">Loading procurement requirements...</div>
      ) : requirements.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📋</div>
          <h3>No Procurement Demands Active</h3>
          <p>Buyers have not posted active purchase demands in this category yet.</p>
          {isAuthenticated && isBuyer ? (
            <button className="btn-primary" onClick={() => onNavigate('create-requirement')}>
              Post Procurement Requirement
            </button>
          ) : (
            <button className="btn-secondary" onClick={() => onNavigate('marketplace')}>
              Explore Produce Lots Instead
            </button>
          )}
        </div>
      ) : (
        <div className="requirements-grid">
          {requirements.map((req) => (
            <div key={req.id} className="card requirement-card">
              <div className="lot-header">
                <span className={`category-tag cat-${req.commodity_category}`}>
                  {req.commodity_category.toUpperCase()}
                </span>
                <span className={`status-pill status-${req.status}`}>{req.status.toUpperCase()}</span>
              </div>

              <h3 className="req-commodity-title">{req.commodity_name}</h3>

              <div className="req-details-grid">
                <div className="detail-row">
                  <span className="detail-label">Quantity Needed:</span>
                  <span className="detail-value font-bold">{req.required_quantity} {req.unit}</span>
                </div>

                {req.target_price_per_unit && (
                  <div className="detail-row">
                    <span className="detail-label">Target Price:</span>
                    <span className="detail-price">₹{req.target_price_per_unit.toLocaleString('en-IN')}/{req.unit}</span>
                  </div>
                )}

                {req.minimum_quality_grade && (
                  <div className="detail-row">
                    <span className="detail-label">Min Quality Grade:</span>
                    <span className="grade-badge">{req.minimum_quality_grade}</span>
                  </div>
                )}

                {req.delivery_by && (
                  <div className="detail-row">
                    <span className="detail-label">Delivery Target:</span>
                    <span className="detail-value">{new Date(req.delivery_by).toLocaleDateString()}</span>
                  </div>
                )}

                {req.delivery_location && (
                  <div className="detail-row">
                    <span className="detail-label">Delivery Mill/Yard:</span>
                    <span className="detail-value">
                      {req.delivery_location.name} ({req.delivery_location.district}, {req.delivery_location.state})
                    </span>
                  </div>
                )}
              </div>

              <div className="req-footer">
                <div className="buyer-meta">
                  <span className="buyer-name">{req.buyer_organization || req.buyer_name}</span>
                  {req.buyer_verification_status === 'verified' && (
                    <span className="badge-verified-sm" title="Verified Buyer">✓</span>
                  )}
                </div>
                {user?.roles.includes('farmer') || user?.roles.includes('fpo') ? (
                  <button
                    className="btn-secondary btn-sm"
                    onClick={() => onNavigate('create-lot')}
                  >
                    List Produce to Match
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
