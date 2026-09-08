import React, { useEffect, useState } from 'react';
import { api, type Commodity } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface CreateRequirementViewProps {
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const CreateRequirementView: React.FC<CreateRequirementViewProps> = ({ onNavigate }) => {
  const { profile } = useAuth();
  const [commodities, setCommodities] = useState<Commodity[]>([]);
  const [loadingCommodities, setLoadingCommodities] = useState(true);

  // Form State
  const [commodityId, setCommodityId] = useState('');
  const [requiredQuantity, setRequiredQuantity] = useState('');
  const [unit, setUnit] = useState('quintal');
  const [minimumQualityGrade, setMinimumQualityGrade] = useState('Grade A');
  const [targetPrice, setTargetPrice] = useState('');
  const [deliveryBy, setDeliveryBy] = useState('');

  // Delivery Location
  const [locName, setLocName] = useState(profile?.primary_location?.name || 'Processing Mill / Warehouse');
  const [district, setDistrict] = useState(profile?.primary_location?.district || '');
  const [state, setState] = useState(profile?.primary_location?.state || 'Maharashtra');
  const [postalCode, setPostalCode] = useState(profile?.primary_location?.postal_code || '');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadComms = async () => {
      try {
        const data = await api.getCommodities();
        setCommodities(data);
        if (data.length > 0) {
          setCommodityId(data[0].id);
          setUnit(data[0].default_unit);
        }
      } catch (err) {
        console.error('Failed to load commodities:', err);
      } finally {
        setLoadingCommodities(false);
      }
    };
    loadComms();
  }, []);

  const handleCommodityChange = (id: string) => {
    setCommodityId(id);
    const comm = commodities.find((c) => c.id === id);
    if (comm) {
      setUnit(comm.default_unit);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await api.createBuyerRequirement({
        commodity_id: commodityId,
        required_quantity: Number(requiredQuantity),
        unit,
        minimum_quality_grade: minimumQualityGrade || undefined,
        target_price_per_unit: targetPrice ? Number(targetPrice) : undefined,
        delivery_by: deliveryBy || undefined,
        delivery_location: {
          name: locName,
          district: district || undefined,
          state,
          postal_code: postalCode || undefined,
        },
      });

      onNavigate('requirements');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to post procurement requirement.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="create-lot-page section-container">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Post Procurement Requirement</h1>
          <p className="page-subtitle">
            Publish your bulk agricultural crop demand to direct farmers and FPOs across India.
          </p>
        </div>
        <button className="btn-secondary" onClick={() => onNavigate('requirements')}>
          Cancel
        </button>
      </div>

      {error && <div className="alert-box alert-error">{error}</div>}

      <form onSubmit={handleSubmit} className="form-card">
        <div className="form-section">
          <h2 className="form-section-title">1. Crop Demand Details</h2>

          <div className="form-row">
            <div className="form-group flex-2">
              <label htmlFor="commodityId">Select Crop Commodity *</label>
              {loadingCommodities ? (
                <div>Loading commodities...</div>
              ) : (
                <select
                  id="commodityId"
                  required
                  value={commodityId}
                  onChange={(e) => handleCommodityChange(e.target.value)}
                  className="form-select"
                >
                  {commodities.map((c) => (
                    <option key={c.id} value={c.id}>
                      [{c.category.toUpperCase()}] {c.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="form-group flex-1">
              <label htmlFor="unit">Trade Unit *</label>
              <input
                id="unit"
                type="text"
                required
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                className="form-input"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="requiredQuantity">Required Quantity ({unit}) *</label>
              <input
                id="requiredQuantity"
                type="number"
                required
                step="any"
                min="0.01"
                placeholder="e.g. 1000"
                value={requiredQuantity}
                onChange={(e) => setRequiredQuantity(e.target.value)}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="targetPrice">Target Price Per Unit (₹/{unit})</label>
              <input
                id="targetPrice"
                type="number"
                step="any"
                min="0"
                placeholder="e.g. 2300 (Optional)"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
                className="form-input"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="minimumQualityGrade">Minimum Quality Grade</label>
              <select
                id="minimumQualityGrade"
                value={minimumQualityGrade}
                onChange={(e) => setMinimumQualityGrade(e.target.value)}
                className="form-select"
              >
                <option value="Grade A">Grade A (Premium / Export / Top Quality)</option>
                <option value="Grade B">Grade B (Standard Commercial / Mandi Grade)</option>
                <option value="Organic Certified">Organic Certified</option>
                <option value="Fair Average Quality">Fair Average Quality (FAQ)</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="deliveryBy">Delivery Target Date</label>
              <input
                id="deliveryBy"
                type="date"
                value={deliveryBy}
                onChange={(e) => setDeliveryBy(e.target.value)}
                className="form-input"
              />
            </div>
          </div>
        </div>

        <div className="form-section">
          <h2 className="form-section-title">2. Destination Delivery Location</h2>

          <div className="form-group">
            <label htmlFor="locName">Delivery Hub / Mill Name *</label>
            <input
              id="locName"
              type="text"
              required
              placeholder="e.g. Pune Central Processing Facility"
              value={locName}
              onChange={(e) => setLocName(e.target.value)}
              className="form-input"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="district">District *</label>
              <input
                id="district"
                type="text"
                required
                placeholder="e.g. Pune"
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="state">State *</label>
              <input
                id="state"
                type="text"
                required
                placeholder="e.g. Maharashtra"
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="postalCode">PIN Code</label>
              <input
                id="postalCode"
                type="text"
                placeholder="e.g. 411001"
                value={postalCode}
                onChange={(e) => setPostalCode(e.target.value)}
                className="form-input"
              />
            </div>
          </div>
        </div>

        <div className="form-actions-bar">
          <button type="button" className="btn-secondary" onClick={() => onNavigate('requirements')}>
            Cancel
          </button>
          <button type="submit" className="btn-primary btn-lg" disabled={submitting}>
            {submitting ? 'Posting Procurement Demand...' : 'Post Procurement Requirement ➔'}
          </button>
        </div>
      </form>
    </div>
  );
};
