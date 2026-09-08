import React from 'react';
import type { ProduceLotSummary } from '../../api/client';

export interface ProduceLotCardProps {
  lot: ProduceLotSummary;
  onViewLot: (lotId: string) => void;
}

export const ProduceLotCard: React.FC<ProduceLotCardProps> = ({ lot, onViewLot }) => {
  const isNegotiable = lot.price_mode === 'NEGOTIABLE' || !lot.asking_price_per_unit;
  const isSold = lot.status === 'sold';
  const isCancelled = lot.status === 'cancelled';
  const isInactive = isSold || isCancelled;

  // Format Pickup Location
  const locationText = lot.pickup_location
    ? lot.pickup_location.district
      ? `${lot.pickup_location.district}, ${lot.pickup_location.state}`
      : `${lot.pickup_location.name}, ${lot.pickup_location.state}`
    : 'Location not specified';

  // Role display
  const sellerRoleLabel = lot.seller_role?.toLowerCase() === 'fpo' ? 'FPO' : 'Farmer';

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onViewLot(lot.id);
    }
  };

  return (
    <article
      className={`produce-card ${isInactive ? 'is-inactive' : ''}`}
      onClick={() => onViewLot(lot.id)}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="article"
      aria-label={`${lot.title} - ${lot.commodity_name}`}
    >
      {/* 1. Header Row: Category & Status */}
      <div className="produce-card-header">
        <span className={`produce-category-tag cat-${lot.commodity_category}`}>
          {lot.commodity_category.replace('_', ' ').toUpperCase()}
        </span>
        <span className={`produce-status-badge status-${lot.status}`}>
          {lot.status.toUpperCase()}
        </span>
      </div>

      {/* 2. Title & Commodity Subtitle */}
      <div className="produce-card-title-section">
        <h3 className="produce-card-title">{lot.title}</h3>
        <p className="produce-card-commodity">{lot.commodity_name}</p>
      </div>

      {/* 3. Primary Metrics Block (Quantity & Price) */}
      <div className="produce-card-metrics-grid">
        <div className="produce-metric-box">
          <span className="metric-label">Available</span>
          <span className="metric-value">
            {Number(lot.available_quantity).toLocaleString('en-IN', { maximumFractionDigits: 3 })} {lot.unit}
          </span>
        </div>

        <div className="produce-metric-box price-metric-box">
          <span className="metric-label">Price</span>
          {isNegotiable ? (
            <div className="price-negotiable-wrap">
              <span className="metric-value price-dash">₹ —</span>
              <span className="badge-negotiable">NEGOTIABLE</span>
            </div>
          ) : (
            <span className="metric-value price-fixed">
              ₹{Number(lot.asking_price_per_unit).toLocaleString('en-IN')}{' '}
              <span className="price-unit">/ {lot.unit}</span>
            </span>
          )}
        </div>
      </div>

      {/* 4. Specifications Meta (Quality, Location, Aggregation) */}
      <div className="produce-card-meta-list">
        {lot.quality_grade && (
          <div className="meta-item">
            <span className="meta-label">Quality:</span>
            <span className="meta-value quality-badge">{lot.quality_grade}</span>
          </div>
        )}

        <div className="meta-item">
          <span className="meta-label">Pickup:</span>
          <span className="meta-value">{locationText}</span>
        </div>

        {lot.is_aggregated && (
          <div className="meta-item aggregated-item">
            <span className="meta-label">Batch:</span>
            <span className="meta-value aggregated-badge">
              FPO Aggregated ({lot.contributions_count} members)
            </span>
          </div>
        )}
      </div>

      {/* 5. Footer: Seller Info & Primary Action */}
      <div className="produce-card-footer">
        <div className="seller-profile-group">
          <div className="seller-name-row">
            <span className="seller-name-label">Seller:</span>
            <span className="seller-name-val">{lot.seller_name}</span>
          </div>
          <div className="seller-provenance-row">
            <span className="seller-role-tag">{sellerRoleLabel}</span>
            {lot.seller_verification_status === 'verified' && (
              <span className="badge-verified" title="Verified Producer">
                ✓ VERIFIED
              </span>
            )}
            {lot.seller_verification_status === 'pending' && (
              <span className="badge-pending" title="Verification Pending">
                PENDING
              </span>
            )}
            {lot.seller_verification_status === 'rejected' && (
              <span className="badge-unverified" title="Unverified Producer">
                UNVERIFIED
              </span>
            )}
          </div>
        </div>

        <button
          type="button"
          className="btn-primary btn-view-lot"
          onClick={(e) => {
            e.stopPropagation();
            onViewLot(lot.id);
          }}
          disabled={isInactive}
        >
          {isSold ? 'Sold' : 'View Lot'}
        </button>
      </div>
    </article>
  );
};
