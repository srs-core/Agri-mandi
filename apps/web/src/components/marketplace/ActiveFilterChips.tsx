import React from 'react';

export interface ActiveFiltersProps {
  category: string;
  categoryLabel?: string;
  commodityName?: string;
  stateFilter: string;
  districtFilter: string;
  qualityGrade: string;
  minPrice: string;
  maxPrice: string;
  minQuantity?: string;
  sellerRole: string;
  onRemoveCategory: () => void;
  onRemoveCommodity: () => void;
  onRemoveState: () => void;
  onRemoveDistrict: () => void;
  onRemoveQualityGrade: () => void;
  onRemoveMinPrice: () => void;
  onRemoveMaxPrice: () => void;
  onRemoveMinQuantity: () => void;
  onRemoveSellerRole: () => void;
  onResetAll: () => void;
}

export const ActiveFilterChips: React.FC<ActiveFiltersProps> = ({
  category,
  categoryLabel,
  commodityName,
  stateFilter,
  districtFilter,
  qualityGrade,
  minPrice,
  maxPrice,
  minQuantity,
  sellerRole,
  onRemoveCategory,
  onRemoveCommodity,
  onRemoveState,
  onRemoveDistrict,
  onRemoveQualityGrade,
  onRemoveMinPrice,
  onRemoveMaxPrice,
  onRemoveMinQuantity,
  onRemoveSellerRole,
  onResetAll,
}) => {
  const activeChips: { id: string; label: string; onRemove: () => void }[] = [];

  if (category) {
    activeChips.push({
      id: 'category',
      label: `Category: ${categoryLabel || category}`,
      onRemove: onRemoveCategory,
    });
  }

  if (commodityName) {
    activeChips.push({
      id: 'commodity',
      label: `Crop: ${commodityName}`,
      onRemove: onRemoveCommodity,
    });
  }

  if (stateFilter) {
    activeChips.push({
      id: 'state',
      label: `State: ${stateFilter}`,
      onRemove: onRemoveState,
    });
  }

  if (districtFilter) {
    activeChips.push({
      id: 'district',
      label: `District: ${districtFilter}`,
      onRemove: onRemoveDistrict,
    });
  }

  if (qualityGrade) {
    activeChips.push({
      id: 'quality',
      label: `Quality: ${qualityGrade}`,
      onRemove: onRemoveQualityGrade,
    });
  }

  if (minPrice && maxPrice) {
    activeChips.push({
      id: 'price-range',
      label: `Price: ₹${minPrice} - ₹${maxPrice}/unit`,
      onRemove: () => {
        onRemoveMinPrice();
        onRemoveMaxPrice();
      },
    });
  } else if (minPrice) {
    activeChips.push({
      id: 'min-price',
      label: `Min Price: ₹${minPrice}/unit`,
      onRemove: onRemoveMinPrice,
    });
  } else if (maxPrice) {
    activeChips.push({
      id: 'max-price',
      label: `Max Price: ₹${maxPrice}/unit`,
      onRemove: onRemoveMaxPrice,
    });
  }

  if (minQuantity) {
    activeChips.push({
      id: 'min-quantity',
      label: `Min Quantity: ${minQuantity}`,
      onRemove: onRemoveMinQuantity,
    });
  }

  if (sellerRole) {
    const roleLabel = sellerRole === 'farmer' ? 'Individual Farmer' : sellerRole === 'fpo' ? 'FPO / Cooperative' : sellerRole;
    activeChips.push({
      id: 'seller-role',
      label: `Seller: ${roleLabel}`,
      onRemove: onRemoveSellerRole,
    });
  }

  if (activeChips.length === 0) {
    return null;
  }

  return (
    <div className="active-filters-container" aria-label="Active marketplace filters">
      <span className="active-filters-label">Filters:</span>
      <div className="active-filter-chips-list">
        {activeChips.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className="active-filter-chip"
            onClick={chip.onRemove}
            title={`Remove ${chip.label}`}
            aria-label={`Remove filter ${chip.label}`}
          >
            <span className="chip-text">{chip.label}</span>
            <span className="chip-remove-icon" aria-hidden="true">✕</span>
          </button>
        ))}

        <button
          type="button"
          className="active-filters-reset-btn"
          onClick={onResetAll}
        >
          Reset filters
        </button>
      </div>
    </div>
  );
};
