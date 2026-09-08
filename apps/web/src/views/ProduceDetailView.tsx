import React, { useEffect, useState } from 'react';
import { api, type ProduceLotDetail } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface ProduceDetailViewProps {
  lotId: string;
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const ProduceDetailView: React.FC<ProduceDetailViewProps> = ({ lotId, onNavigate }) => {
  const { user, isAuthenticated } = useAuth();
  const [lot, setLot] = useState<ProduceLotDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Make Offer State
  const [showOfferModal, setShowOfferModal] = useState(false);
  const [offeredQuantity, setOfferedQuantity] = useState<string>('');
  const [offeredPrice, setOfferedPrice] = useState<string>('');
  const [offeredNotes, setOfferedNotes] = useState<string>('');
  const [submittingOffer, setSubmittingOffer] = useState(false);
  const [offerSuccess, setOfferSuccess] = useState<string | null>(null);
  const [offerError, setOfferError] = useState<string | null>(null);
  const [quantityError, setQuantityError] = useState<string | null>(null);
  const [priceError, setPriceError] = useState<string | null>(null);

  useEffect(() => {
    const fetchLot = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getProduceLot(lotId);
        setLot(data);
        setOfferedQuantity(String(data.available_quantity));
        if (data.asking_price_per_unit) {
          setOfferedPrice(String(data.asking_price_per_unit));
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load produce lot details.');
      } finally {
        setLoading(false);
      }
    };
    fetchLot();
  }, [lotId]);

  const validateQuantity = (val: string): string | null => {
    if (!val.trim()) return 'Enter a quantity';
    const num = Number(val);
    if (isNaN(num)) return 'Enter a valid number';
    if (num <= 0) return 'Quantity must be greater than 0';
    if (lot && num > Number(lot.available_quantity)) {
      return `Offered quantity cannot exceed the available ${lot.available_quantity} ${lot.unit}.`;
    }
    return null;
  };

  const validatePrice = (val: string): string | null => {
    if (!val.trim()) return lot ? `Enter an offered price per ${lot.unit}.` : 'Enter a price';
    const num = Number(val);
    if (isNaN(num)) return 'Enter a valid price';
    if (num <= 0) return lot ? `Enter a valid offered price per ${lot.unit}.` : 'Price must be greater than 0';
    return null;
  };

  const openOfferModal = () => {
    if (!lot) return;
    setOfferedQuantity(String(lot.available_quantity));
    setOfferedPrice(lot.asking_price_per_unit ? String(lot.asking_price_per_unit) : '');
    setOfferedNotes('');
    setQuantityError(null);
    setPriceError(null);
    setOfferError(null);
    setOfferSuccess(null);
    setShowOfferModal(true);
  };

  const closeOfferModal = () => {
    setShowOfferModal(false);
    setQuantityError(null);
    setPriceError(null);
    setOfferError(null);
    setOfferSuccess(null);
  };

  const handleQuantityChange = (val: string) => {
    setOfferedQuantity(val);
    setQuantityError(validateQuantity(val));
  };

  const handlePriceChange = (val: string) => {
    setOfferedPrice(val);
    setPriceError(validatePrice(val));
  };

  const handleOfferSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setOfferError(null);
    setOfferSuccess(null);

    // Pre-submit validation
    const qtyErr = validateQuantity(offeredQuantity);
    const prcErr = validatePrice(offeredPrice);
    setQuantityError(qtyErr);
    setPriceError(prcErr);
    if (qtyErr || prcErr) return;

    setSubmittingOffer(true);
    try {
      await api.createOffer({
        produce_lot_id: lotId,
        offered_quantity: Number(offeredQuantity),
        offered_price_per_unit: Number(offeredPrice),
        notes: offeredNotes.trim() || undefined,
      });
      setOfferSuccess('Commercial offer successfully submitted to the seller!');
      setTimeout(() => {
        closeOfferModal();
        onNavigate('offers');
      }, 1500);
    } catch (err: unknown) {
      setOfferError(err instanceof Error ? err.message : 'Failed to submit offer.');
    } finally {
      setSubmittingOffer(false);
    }
  };

  if (loading) {
    return <div className="section-container loading-spinner">Loading produce lot #{lotId}...</div>;
  }

  if (error || !lot) {
    return (
      <div className="section-container">
        <div className="alert-box alert-error">{error || 'Produce listing not found.'}</div>
        <button className="btn-secondary" onClick={() => onNavigate('marketplace')}>
          Back to Marketplace
        </button>
      </div>
    );
  }

  const isOwner = user?.id === lot.seller_user_id;
  const isBuyer = user?.roles.includes('buyer');
  const isNegotiable = lot.price_mode === 'NEGOTIABLE' || !lot.asking_price_per_unit;
  const totalAskingValue = lot.asking_price_per_unit
    ? lot.available_quantity * lot.asking_price_per_unit
    : null;
  const offerTotal = (Number(offeredQuantity) || 0) * (Number(offeredPrice) || 0);
  const isOfferTotalValid = !quantityError && !priceError &&
    offeredQuantity.trim() !== '' && offeredPrice.trim() !== '' &&
    Number(offeredQuantity) > 0 && Number(offeredPrice) > 0;
  const isFormValid = isOfferTotalValid && !submittingOffer;

  return (
    <div className="produce-detail-page section-container">
      {/* Breadcrumb */}
      <div className="breadcrumb-nav">
        <button className="btn-link" onClick={() => onNavigate('marketplace')}>
          ← Back to Marketplace
        </button>
        <span>/</span>
        <span className="breadcrumb-current">{lot.title}</span>
      </div>

      <div className="detail-layout-grid">
        {/* Left Column: Produce & Seller Specs */}
        <div className="detail-main-col">
          <div className="card detail-header-card">
            <div className="lot-header">
              <span className={`category-tag cat-${lot.commodity_category}`}>
                {lot.commodity_category.toUpperCase()}
              </span>
              <span className={`status-pill status-${lot.status}`}>{lot.status.toUpperCase()}</span>
            </div>

            <h1 className="detail-title">{lot.title}</h1>
            <div className="detail-commodity-name">Commodity: {lot.commodity_name}</div>

            <div className="key-metrics-row">
              <div className="key-metric-box">
                <span className="metric-label">Available Quantity</span>
                <span className="metric-value">{lot.available_quantity} {lot.unit}</span>
              </div>

              <div className="key-metric-box">
                <span className="metric-label">Asking Price</span>
                <span className="metric-value price-text">
                  {lot.asking_price_per_unit ? `₹${lot.asking_price_per_unit.toLocaleString('en-IN')}/${lot.unit}` : 'Negotiable'}
                </span>
              </div>

              {totalAskingValue && (
                <div className="key-metric-box">
                  <span className="metric-label">Estimated Total Lot Value</span>
                  <span className="metric-value">₹{totalAskingValue.toLocaleString('en-IN')}</span>
                </div>
              )}
            </div>
          </div>

          {/* Quality & Specifications */}
          <div className="card detail-section-card">
            <h2 className="section-subtitle-dark">Quality & Specifications</h2>
            <div className="specs-grid">
              <div className="spec-item">
                <span className="spec-label">Quality Grade:</span>
                <span className="spec-val font-semibold">{lot.quality_grade || 'Standard Field Grade'}</span>
              </div>
              <div className="spec-item">
                <span className="spec-label">Available From:</span>
                <span className="spec-val">{new Date(lot.available_from).toLocaleDateString()}</span>
              </div>
              {lot.available_until && (
                <div className="spec-item">
                  <span className="spec-label">Available Until:</span>
                  <span className="spec-val">{new Date(lot.available_until).toLocaleDateString()}</span>
                </div>
              )}
              <div className="spec-item">
                <span className="spec-label">Batch Type:</span>
                <span className="spec-val">{lot.is_aggregated ? 'FPO Aggregated Batch' : 'Single Farmer Lot'}</span>
              </div>
            </div>

            {lot.quality_notes && (
              <div className="quality-notes-box">
                <h4>Producer Quality & Harvest Notes</h4>
                <p>{lot.quality_notes}</p>
              </div>
            )}
          </div>

          {/* Pickup Location */}
          <div className="card detail-section-card">
            <h2 className="section-subtitle-dark">Farm-Gate Pickup Location</h2>
            {lot.pickup_location ? (
              <div className="location-info-card">
                <div className="loc-name">📍 {lot.pickup_location.name}</div>
                <div className="loc-address">
                  {[
                    lot.pickup_location.village,
                    lot.pickup_location.taluka,
                    lot.pickup_location.district,
                    lot.pickup_location.state,
                    lot.pickup_location.postal_code,
                  ]
                    .filter(Boolean)
                    .join(', ')}
                </div>
              </div>
            ) : (
              <p>Pickup location available upon deal confirmation.</p>
            )}
          </div>

          {/* Aggregated contributions if FPO */}
          {lot.is_aggregated && lot.contributions.length > 0 && (
            <div className="card detail-section-card">
              <h2 className="section-subtitle-dark">FPO Aggregated Member Contributions ({lot.contributions.length})</h2>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Contribution #</th>
                    <th>Contributed Quantity</th>
                  </tr>
                </thead>
                <tbody>
                  {lot.contributions.map((c, idx) => (
                    <tr key={c.id}>
                      <td>Member Contribution {idx + 1}</td>
                      <td>{c.contributed_quantity} {lot.unit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column: Seller Profile & Commercial Actions */}
        <div className="detail-sidebar-col">
          {/* Seller Profile Card */}
          <div className="card seller-profile-card">
            <h3>Seller Information</h3>
            <div className="seller-profile-row">
              <div className="seller-avatar">👨‍🌾</div>
              <div>
                <div className="seller-name-large">{lot.seller_name}</div>
                <div className="seller-type-tag">
                  {lot.seller_role === 'fpo' ? 'Farmer Producer Org' : 'Agricultural Farmer'}
                </div>
              </div>
            </div>

            <div className="seller-verification-row">
              <span className="verify-label">Verification Status:</span>
              <span className={`status-pill status-${lot.seller_verification_status}`}>
                {lot.seller_verification_status === 'verified' ? '✓ Verified Producer' : 'Pending Verification'}
              </span>
            </div>

            {isAuthenticated && (lot.seller_phone || lot.seller_email) && (
              <div className="seller-contact-details">
                {lot.seller_phone && <div>📞 {lot.seller_phone}</div>}
                {lot.seller_email && <div>✉️ {lot.seller_email}</div>}
              </div>
            )}
          </div>

          {/* Action Box */}
          <div className="card action-box-card">
            <h3>Trade Actions</h3>

            {isOwner ? (
              <div className="owner-actions">
                <p className="subtext">You listed this produce lot.</p>
                <button
                  className="btn-secondary btn-block"
                  onClick={() => onNavigate('offers', { lotId: lot.id })}
                >
                  View Incoming Offers for this Lot
                </button>
              </div>
            ) : isBuyer ? (
              <div className="buyer-actions">
                <p className="action-help-text">
                  Submit a binding purchase offer directly to the seller with your desired quantity and price per unit.
                </p>
                <button
                  className="btn-primary btn-block btn-lg"
                  onClick={openOfferModal}
                  disabled={lot.status !== 'published' || lot.available_quantity <= 0}
                >
                  Make Commercial Offer ➔
                </button>
              </div>
            ) : !isAuthenticated ? (
              <div className="guest-actions">
                <p className="action-help-text">
                  Sign in or register as a verified buyer to submit offers on this produce lot.
                </p>
                <button className="btn-primary btn-block" onClick={() => onNavigate('login')}>
                  Sign In to Make Offer
                </button>
                <button className="btn-secondary btn-block" onClick={() => onNavigate('register', { role: 'buyer' })}>
                  Register as Buyer
                </button>
              </div>
            ) : (
              <div className="non-buyer-notice">
                <p>You are logged in as <strong>{user?.roles.join(', ')}</strong>. To make commercial purchase offers, sign in with a Buyer account.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Make Offer Modal */}
      {showOfferModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>Submit Trade Offer</h2>
              <button className="btn-close" onClick={closeOfferModal}>✕</button>
            </div>

            {offerError && <div className="alert-box alert-error">{offerError}</div>}
            {offerSuccess && <div className="alert-box alert-success">{offerSuccess}</div>}

            <form onSubmit={handleOfferSubmit} className="modal-form">
              <div className="modal-lot-summary">
                <strong>Lot:</strong> {lot.title} ({lot.commodity_name})<br />
                <strong>Max Available:</strong> {lot.available_quantity} {lot.unit}
              </div>

              <div className="form-group">
                <label htmlFor="offeredQuantity">Offered Quantity ({lot.unit})</label>
                <input
                  id="offeredQuantity"
                  type="number"
                  required
                  step="0.001"
                  min="0.01"
                  max={lot.available_quantity}
                  value={offeredQuantity}
                  onChange={(e) => handleQuantityChange(e.target.value)}
                  className={`form-input${quantityError ? ' input-error' : ''}`}
                />
                {quantityError && (
                  <div className="field-error-text" role="alert">{quantityError}</div>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="offeredPrice">
                  Offered Price Per Unit (₹/{lot.unit})
                  {!isNegotiable && (
                    <span className="subtext" style={{ marginLeft: '0.5rem', fontWeight: 400 }}>
                      (Fixed Price)
                    </span>
                  )}
                </label>
                <input
                  id="offeredPrice"
                  type="number"
                  required
                  step="0.01"
                  min="0.01"
                  readOnly={!isNegotiable}
                  value={offeredPrice}
                  onChange={(e) => handlePriceChange(e.target.value)}
                  className={`form-input${priceError ? ' input-error' : ''}${!isNegotiable ? ' input-readonly' : ''}`}
                />
                {priceError && (
                  <div className="field-error-text" role="alert">{priceError}</div>
                )}
              </div>

              <div className="form-group">
                <label htmlFor="offeredNotes">Proposal Notes (Optional)</label>
                <textarea
                  id="offeredNotes"
                  rows={2}
                  value={offeredNotes}
                  onChange={(e) => setOfferedNotes(e.target.value)}
                  placeholder="e.g. Bulk purchase with standard payment terms."
                  className="form-textarea"
                />
              </div>

              <div className="offer-total-banner">
                <span className="total-label">Total Commercial Deal Value:</span>
                <span className="total-val">
                  {isOfferTotalValid
                    ? `₹${offerTotal.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
                    : '—'}
                </span>
                {!isOfferTotalValid && (
                  <div className="total-hint">Enter valid quantity and price to calculate total value</div>
                )}
              </div>

              <div className="modal-actions-row">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={closeOfferModal}
                  disabled={submittingOffer}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={!isFormValid}>
                  {submittingOffer ? 'Submitting Offer...' : 'Send Binding Offer to Producer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
