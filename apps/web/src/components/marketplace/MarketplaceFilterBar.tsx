import React, { useState } from 'react';
import type { Commodity } from '../../api/client';
import { FilterDropdown } from './FilterDropdown';

export interface MarketplaceFilterBarProps {
  category: string;
  setCategory: (val: string) => void;
  stateFilter: string;
  setStateFilter: (val: string) => void;
  districtFilter: string;
  setDistrictFilter: (val: string) => void;
  qualityGrade: string;
  setQualityGrade: (val: string) => void;
  minPrice: string;
  setMinPrice: (val: string) => void;
  maxPrice: string;
  setMaxPrice: (val: string) => void;
  minQuantity?: string;
  setMinQuantity?: (val: string) => void;
  sellerRole: string;
  setSellerRole: (val: string) => void;
  commodityId: string;
  setCommodityId: (val: string) => void;
  commodities: Commodity[];
  onResetFilters: () => void;
}

const CATEGORY_OPTIONS = [
  { value: '', label: 'All Categories' },
  { value: 'vegetables', label: 'Vegetables' },
  { value: 'fruits', label: 'Fruits' },
  { value: 'grains', label: 'Grains' },
  { value: 'pulses', label: 'Pulses' },
  { value: 'spices', label: 'Spices' },
  { value: 'other_crops', label: 'Commercial Crops' },
];

const QUALITY_OPTIONS = [
  { value: '', label: 'Any Grade' },
  { value: 'Grade A', label: 'Grade A' },
  { value: 'Grade B', label: 'Grade B' },
  { value: 'Grade C', label: 'Grade C' },
  { value: 'Organic', label: 'Organic' },
  { value: 'Export Quality', label: 'Export Quality' },
];

const POPULAR_STATES = ['Maharashtra', 'Punjab', 'Madhya Pradesh', 'Gujarat', 'Karnataka', 'Uttar Pradesh'];

export const MarketplaceFilterBar: React.FC<MarketplaceFilterBarProps> = ({
  category,
  setCategory,
  stateFilter,
  setStateFilter,
  districtFilter,
  setDistrictFilter,
  qualityGrade,
  setQualityGrade,
  minPrice,
  setMinPrice,
  maxPrice,
  setMaxPrice,
  minQuantity = '',
  setMinQuantity,
  sellerRole,
  setSellerRole,
  commodityId,
  setCommodityId,
  commodities,
  onResetFilters,
}) => {
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);

  // Local draft states for panels with apply/clear buttons
  const [localState, setLocalState] = useState(stateFilter);
  const [localDistrict, setLocalDistrict] = useState(districtFilter);
  const [localMinPrice, setLocalMinPrice] = useState(minPrice);
  const [localMaxPrice, setLocalMaxPrice] = useState(maxPrice);
  const [localMinQty, setLocalMinQty] = useState(minQuantity);

  const toggleDropdown = (name: string) => {
    if (openDropdown === name) {
      setOpenDropdown(null);
    } else {
      // Sync local drafts when opening
      if (name === 'location') {
        setLocalState(stateFilter);
        setLocalDistrict(districtFilter);
      } else if (name === 'price') {
        setLocalMinPrice(minPrice);
        setLocalMaxPrice(maxPrice);
      } else if (name === 'more') {
        setLocalMinQty(minQuantity);
      }
      setOpenDropdown(name);
    }
  };

  const closeDropdown = () => setOpenDropdown(null);

  // Calculate active states & summary labels
  const selectedCategoryObj = CATEGORY_OPTIONS.find((c) => c.value === category);
  const categorySummary = category ? selectedCategoryObj?.label : undefined;

  const locationIsActive = Boolean(stateFilter || districtFilter);
  const locationSummary = stateFilter
    ? districtFilter
      ? `${districtFilter}, ${stateFilter}`
      : stateFilter
    : districtFilter
    ? districtFilter
    : undefined;

  const qualityIsActive = Boolean(qualityGrade);
  const qualitySummary = qualityGrade || undefined;

  const priceIsActive = Boolean(minPrice || maxPrice);
  const priceSummary =
    minPrice && maxPrice
      ? `₹${minPrice}–₹${maxPrice}`
      : minPrice
      ? `≥₹${minPrice}`
      : maxPrice
      ? `≤₹${maxPrice}`
      : undefined;

  const moreActiveCount =
    (sellerRole ? 1 : 0) + (commodityId ? 1 : 0) + (minQuantity ? 1 : 0);
  const moreIsActive = moreActiveCount > 0;
  const moreSummary = moreActiveCount > 0 ? `(${moreActiveCount})` : undefined;

  const hasAnyFilterActive =
    Boolean(category) ||
    locationIsActive ||
    qualityIsActive ||
    priceIsActive ||
    moreIsActive;

  // Handle Location Apply / Clear
  const handleApplyLocation = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setStateFilter(localState.trim());
    setDistrictFilter(localDistrict.trim());
    closeDropdown();
  };

  const handleClearLocation = () => {
    setLocalState('');
    setLocalDistrict('');
    setStateFilter('');
    setDistrictFilter('');
    closeDropdown();
  };

  // Handle Price Apply / Clear
  const handleApplyPrice = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setMinPrice(localMinPrice.trim());
    setMaxPrice(localMaxPrice.trim());
    closeDropdown();
  };

  const handleClearPrice = () => {
    setLocalMinPrice('');
    setLocalMaxPrice('');
    setMinPrice('');
    setMaxPrice('');
    closeDropdown();
  };

  // Handle More Filters Apply / Clear
  const handleApplyMore = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (setMinQuantity) {
      setMinQuantity(localMinQty.trim());
    }
    closeDropdown();
  };

  const handleClearMore = () => {
    setSellerRole('');
    setCommodityId('');
    setLocalMinQty('');
    if (setMinQuantity) setMinQuantity('');
    closeDropdown();
  };

  // Commodities filtered by selected category if any
  const availableCommodities = category
    ? commodities.filter((c) => c.category === category)
    : commodities;

  return (
    <div className="marketplace-filter-bar-container">
      <div className="marketplace-filter-bar" role="toolbar" aria-label="Marketplace filters">
        {/* 1. Category Filter */}
        <FilterDropdown
          label="Category"
          activeSummary={categorySummary}
          isActive={Boolean(category)}
          isOpen={openDropdown === 'category'}
          onToggle={() => toggleDropdown('category')}
          onClose={closeDropdown}
        >
          <div className="filter-panel-menu" role="menu">
            {CATEGORY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                role="menuitem"
                className={`filter-menu-item ${category === opt.value ? 'is-selected' : ''}`}
                onClick={() => {
                  setCategory(opt.value);
                  closeDropdown();
                }}
              >
                <span className="menu-item-check">{category === opt.value ? '✓' : ''}</span>
                <span className="menu-item-text">{opt.label}</span>
              </button>
            ))}
          </div>
        </FilterDropdown>

        {/* 2. Location Filter */}
        <FilterDropdown
          label="Location"
          activeSummary={locationSummary}
          isActive={locationIsActive}
          isOpen={openDropdown === 'location'}
          onToggle={() => toggleDropdown('location')}
          onClose={closeDropdown}
        >
          <form onSubmit={handleApplyLocation} className="filter-panel-form">
            <div className="filter-form-group">
              <label htmlFor="filter-state-input" className="filter-form-label">State / Region</label>
              <input
                id="filter-state-input"
                type="text"
                placeholder="e.g. Maharashtra, Punjab"
                value={localState}
                onChange={(e) => setLocalState(e.target.value)}
                className="form-input filter-form-input"
                autoFocus
              />
              <div className="popular-states-quicklist">
                {POPULAR_STATES.map((st) => (
                  <button
                    key={st}
                    type="button"
                    className={`quick-state-btn ${localState.toLowerCase() === st.toLowerCase() ? 'active' : ''}`}
                    onClick={() => setLocalState(st)}
                  >
                    {st}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-form-group">
              <label htmlFor="filter-district-input" className="filter-form-label">District / City</label>
              <input
                id="filter-district-input"
                type="text"
                placeholder="e.g. Nashik, Pune, Indore"
                value={localDistrict}
                onChange={(e) => setLocalDistrict(e.target.value)}
                className="form-input filter-form-input"
              />
            </div>

            <div className="filter-panel-actions">
              <button
                type="button"
                className="btn-outline btn-xs"
                onClick={handleClearLocation}
              >
                Clear
              </button>
              <button type="submit" className="btn-primary btn-xs">
                Apply Location
              </button>
            </div>
          </form>
        </FilterDropdown>

        {/* 3. Quality Grade Filter */}
        <FilterDropdown
          label="Quality"
          activeSummary={qualitySummary}
          isActive={qualityIsActive}
          isOpen={openDropdown === 'quality'}
          onToggle={() => toggleDropdown('quality')}
          onClose={closeDropdown}
        >
          <div className="filter-panel-menu" role="menu">
            {QUALITY_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                role="menuitem"
                className={`filter-menu-item ${qualityGrade === opt.value ? 'is-selected' : ''}`}
                onClick={() => {
                  setQualityGrade(opt.value);
                  closeDropdown();
                }}
              >
                <span className="menu-item-check">{qualityGrade === opt.value ? '✓' : ''}</span>
                <span className="menu-item-text">{opt.label}</span>
              </button>
            ))}
          </div>
        </FilterDropdown>

        {/* 4. Price Filter */}
        <FilterDropdown
          label="Price"
          activeSummary={priceSummary}
          isActive={priceIsActive}
          isOpen={openDropdown === 'price'}
          onToggle={() => toggleDropdown('price')}
          onClose={closeDropdown}
        >
          <form onSubmit={handleApplyPrice} className="filter-panel-form">
            <div className="filter-price-grid">
              <div className="filter-form-group">
                <label htmlFor="filter-min-price" className="filter-form-label">Min Price (₹/unit)</label>
                <input
                  id="filter-min-price"
                  type="number"
                  min="0"
                  placeholder="Min ₹"
                  value={localMinPrice}
                  onChange={(e) => setLocalMinPrice(e.target.value)}
                  className="form-input filter-form-input"
                  autoFocus
                />
              </div>

              <div className="filter-form-group">
                <label htmlFor="filter-max-price" className="filter-form-label">Max Price (₹/unit)</label>
                <input
                  id="filter-max-price"
                  type="number"
                  min="0"
                  placeholder="Max ₹"
                  value={localMaxPrice}
                  onChange={(e) => setLocalMaxPrice(e.target.value)}
                  className="form-input filter-form-input"
                />
              </div>
            </div>

            <div className="filter-panel-actions">
              <button
                type="button"
                className="btn-outline btn-xs"
                onClick={handleClearPrice}
              >
                Clear
              </button>
              <button type="submit" className="btn-primary btn-xs">
                Apply Price
              </button>
            </div>
          </form>
        </FilterDropdown>

        {/* 5. More Filters */}
        <FilterDropdown
          label="More"
          activeSummary={moreSummary}
          isActive={moreIsActive}
          isOpen={openDropdown === 'more'}
          onToggle={() => toggleDropdown('more')}
          onClose={closeDropdown}
          align="right"
        >
          <form onSubmit={handleApplyMore} className="filter-panel-form filter-panel-more">
            <div className="filter-form-group">
              <label htmlFor="filter-seller-role" className="filter-form-label">Seller Type</label>
              <select
                id="filter-seller-role"
                value={sellerRole}
                onChange={(e) => setSellerRole(e.target.value)}
                className="form-select filter-form-select"
              >
                <option value="">All Sellers</option>
                <option value="farmer">Individual Farmer</option>
                <option value="fpo">FPO / Cooperative</option>
              </select>
            </div>

            <div className="filter-form-group">
              <label htmlFor="filter-commodity" className="filter-form-label">Specific Crop / Commodity</label>
              <select
                id="filter-commodity"
                value={commodityId}
                onChange={(e) => setCommodityId(e.target.value)}
                className="form-select filter-form-select"
              >
                <option value="">All Commodities</option>
                {availableCommodities.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.default_unit})
                  </option>
                ))}
              </select>
            </div>

            {setMinQuantity && (
              <div className="filter-form-group">
                <label htmlFor="filter-min-qty" className="filter-form-label">Min Available Quantity</label>
                <input
                  id="filter-min-qty"
                  type="number"
                  min="0"
                  placeholder="e.g. 50"
                  value={localMinQty}
                  onChange={(e) => setLocalMinQty(e.target.value)}
                  className="form-input filter-form-input"
                />
              </div>
            )}

            <div className="filter-panel-actions">
              <button
                type="button"
                className="btn-outline btn-xs"
                onClick={handleClearMore}
              >
                Clear
              </button>
              <button type="submit" className="btn-primary btn-xs">
                Apply More
              </button>
            </div>
          </form>
        </FilterDropdown>

        {/* 6. Reset Filters Button */}
        {hasAnyFilterActive && (
          <button
            type="button"
            className="filter-bar-reset-btn"
            onClick={onResetFilters}
            title="Reset all active filters"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
};
