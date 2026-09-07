import React, { useEffect, useState } from 'react';
import { api, type Commodity } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface CreateProduceLotViewProps {
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const CreateProduceLotView: React.FC<CreateProduceLotViewProps> = ({ onNavigate }) => {
  const { user, profile } = useAuth();
  const [commodities, setCommodities] = useState<Commodity[]>([]);
  const [loadingCommodities, setLoadingCommodities] = useState(true);

  // Form State
  const [commodityId, setCommodityId] = useState('');
  const [title, setTitle] = useState('');
  const [availableQuantity, setAvailableQuantity] = useState('');
  const [unit, setUnit] = useState('quintal');
  const [qualityGrade, setQualityGrade] = useState('Grade A');
  const [qualityNotes, setQualityNotes] = useState('');
  const [askingPrice, setAskingPrice] = useState('');
  const [availableFrom, setAvailableFrom] = useState(new Date().toISOString().split('T')[0]);
  const [availableUntil, setAvailableUntil] = useState('');

  // Location State (Pre-filled from profile primary location if present)
  const [locName, setLocName] = useState(profile?.primary_location?.name || 'Farm Gate Yard');
  const [village, setVillage] = useState(profile?.primary_location?.village || '');
  const [taluka, setTaluka] = useState(profile?.primary_location?.taluka || '');
  const [district, setDistrict] = useState(profile?.primary_location?.district || '');
  const [state, setState] = useState(profile?.primary_location?.state || 'Maharashtra');
  const [postalCode, setPostalCode] = useState(profile?.primary_location?.postal_code || '');

  // FPO Aggregation state
  const isFPO = user?.roles.includes('fpo');
  const [isAggregated, setIsAggregated] = useState(false);
  const [contributions, setContributions] = useState<Array<{ contributed_quantity: string }>>([
    { contributed_quantity: '' },
  ]);

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
      if (!title) {
        setTitle(`Fresh ${comm.name} - Harvested Lot`);
      }
    }
  };

  const handleAddContribution = () => {
    setContributions([...contributions, { contributed_quantity: '' }]);
  };

  const handleRemoveContribution = (index: number) => {
    setContributions(contributions.filter((_, i) => i !== index));
  };

  const handleContributionChange = (index: number, val: string) => {
    const updated = [...contributions];
    updated[index].contributed_quantity = val;
    setContributions(updated);

    // Auto sum quantity if aggregated
    const sum = updated.reduce((acc, curr) => acc + (Number(curr.contributed_quantity) || 0), 0);
    if (sum > 0) {
      setAvailableQuantity(String(sum));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const validContributions = isAggregated
        ? contributions
            .filter((c) => Number(c.contributed_quantity) > 0)
            .map((c) => ({
              contributed_quantity: Number(c.contributed_quantity),
            }))
        : undefined;

      const created = await api.createProduceLot({
        commodity_id: commodityId,
        title,
        available_quantity: Number(availableQuantity),
        unit,
        quality_grade: qualityGrade || undefined,
        quality_notes: qualityNotes || undefined,
        asking_price_per_unit: askingPrice ? Number(askingPrice) : undefined,
        available_from: availableFrom,
        available_until: availableUntil || undefined,
        pickup_location: {
          name: locName,
          village: village || undefined,
          taluka: taluka || undefined,
          district: district || undefined,
          state,
          postal_code: postalCode || undefined,
        },
        is_aggregated: isAggregated,
        contributions: validContributions,
      });

      onNavigate('produce-detail', { lotId: created.id });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to list produce lot.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="create-lot-page section-container">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">List Produce Lot</h1>
          <p className="page-subtitle">
            Publish your harvested agricultural produce to the live national exchange for direct buyer bidding.
          </p>
        </div>
        <button className="btn-secondary" onClick={() => onNavigate('marketplace')}>
          Cancel
        </button>
      </div>

      {error && <div className="alert-box alert-error">{error}</div>}

      <form onSubmit={handleSubmit} className="form-card">
        {/* Section 1: Commodity & Basic Info */}
        <div className="form-section">
          <h2 className="form-section-title">1. Crop & Produce Information</h2>

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
                      [{c.category.toUpperCase()}] {c.name} (Default: {c.default_unit})
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
                placeholder="quintal, kg, box..."
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="title">Listing Title *</label>
            <input
              id="title"
              type="text"
              required
              placeholder="e.g. Fresh Red Onions - 55mm+ Sun Dried Grade A"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="form-input"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="availableQuantity">Available Quantity ({unit}) *</label>
              <input
                id="availableQuantity"
                type="number"
                required
                step="any"
                min="0.01"
                placeholder="e.g. 500"
                value={availableQuantity}
                onChange={(e) => setAvailableQuantity(e.target.value)}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="askingPrice">Asking Price Per Unit (₹/{unit})</label>
              <input
                id="askingPrice"
                type="number"
                step="any"
                min="0"
                placeholder="e.g. 2400 (leave blank for negotiable)"
                value={askingPrice}
                onChange={(e) => setAskingPrice(e.target.value)}
                className="form-input"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Quality & Dates */}
        <div className="form-section">
          <h2 className="form-section-title">2. Quality Grading & Availability Window</h2>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="qualityGrade">Quality Grade</label>
              <select
                id="qualityGrade"
                value={qualityGrade}
                onChange={(e) => setQualityGrade(e.target.value)}
                className="form-select"
              >
                <option value="Grade A">Grade A (Premium / Export / Top Quality)</option>
                <option value="Grade B">Grade B (Standard Commercial / Mandi Grade)</option>
                <option value="Grade C">Grade C (Processing / Industrial Grade)</option>
                <option value="Organic Certified">Organic Certified</option>
                <option value="Fair Average Quality">Fair Average Quality (FAQ)</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="availableFrom">Available From Date *</label>
              <input
                id="availableFrom"
                type="date"
                required
                value={availableFrom}
                onChange={(e) => setAvailableFrom(e.target.value)}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="availableUntil">Available Until Date (Optional)</label>
              <input
                id="availableUntil"
                type="date"
                value={availableUntil}
                onChange={(e) => setAvailableUntil(e.target.value)}
                className="form-input"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="qualityNotes">Quality & Harvest Specifications</label>
            <textarea
              id="qualityNotes"
              rows={3}
              placeholder="Provide color, size specs, moisture levels, harvesting date, pesticide certification or packaging details..."
              value={qualityNotes}
              onChange={(e) => setQualityNotes(e.target.value)}
              className="form-textarea"
            />
          </div>
        </div>

        {/* Section 3: Farm-Gate Pickup Location */}
        <div className="form-section">
          <h2 className="form-section-title">3. Farm-Gate / Mandi Yard Pickup Location</h2>

          <div className="form-group">
            <label htmlFor="locName">Location / Yard Name *</label>
            <input
              id="locName"
              type="text"
              required
              placeholder="e.g. Pimpalgaon APMC Yard / Green Valley Farm Gate"
              value={locName}
              onChange={(e) => setLocName(e.target.value)}
              className="form-input"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="village">Village / Town</label>
              <input
                id="village"
                type="text"
                placeholder="e.g. Pimpalgaon"
                value={village}
                onChange={(e) => setVillage(e.target.value)}
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="taluka">Taluka / Sub-district</label>
              <input
                id="taluka"
                type="text"
                placeholder="e.g. Niphad"
                value={taluka}
                onChange={(e) => setTaluka(e.target.value)}
                className="form-input"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="district">District *</label>
              <input
                id="district"
                type="text"
                required
                placeholder="e.g. Nashik"
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
              <label htmlFor="postalCode">PIN / Postal Code</label>
              <input
                id="postalCode"
                type="text"
                placeholder="e.g. 422209"
                value={postalCode}
                onChange={(e) => setPostalCode(e.target.value)}
                className="form-input"
              />
            </div>
          </div>
        </div>

        {/* Section 4: FPO Aggregation (If FPO) */}
        {isFPO && (
          <div className="form-section">
            <div className="fpo-checkbox-row">
              <input
                id="isAggregated"
                type="checkbox"
                checked={isAggregated}
                onChange={(e) => setIsAggregated(e.target.checked)}
                className="form-checkbox"
              />
              <label htmlFor="isAggregated" className="checkbox-label">
                <strong>Mark as Aggregated FPO Batch</strong> (Multiple farmer members pooled into one commercial lot)
              </label>
            </div>

            {isAggregated && (
              <div className="aggregated-contributions-box">
                <h4>Member Contributions Pool</h4>
                {contributions.map((c, idx) => (
                  <div key={idx} className="contribution-row">
                    <span className="contrib-label">Member #{idx + 1}:</span>
                    <input
                      type="number"
                      step="any"
                      placeholder={`Quantity in ${unit}`}
                      value={c.contributed_quantity}
                      onChange={(e) => handleContributionChange(idx, e.target.value)}
                      className="form-input contrib-input"
                    />
                    {contributions.length > 1 && (
                      <button
                        type="button"
                        className="btn-danger-sm"
                        onClick={() => handleRemoveContribution(idx)}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={handleAddContribution}
                >
                  + Add Another Member Share
                </button>
              </div>
            )}
          </div>
        )}

        <div className="form-actions-bar">
          <button type="button" className="btn-secondary" onClick={() => onNavigate('marketplace')}>
            Cancel
          </button>
          <button type="submit" className="btn-primary btn-lg" disabled={submitting}>
            {submitting ? 'Publishing Produce Lot...' : 'Publish Produce Lot to Marketplace ➔'}
          </button>
        </div>
      </form>
    </div>
  );
};
