import React, { useEffect, useState } from 'react';
import { api, type Commodity, type ProduceLotSummary } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { MarketplaceFilterBar } from '../components/marketplace/MarketplaceFilterBar';
import { ActiveFilterChips } from '../components/marketplace/ActiveFilterChips';
import { ProduceLotCard } from '../components/marketplace/ProduceLotCard';
import {
  MarketplaceSortControl,
  type SortOptionId,
} from '../components/marketplace/MarketplaceSortControl';
import { MarketplacePagination } from '../components/marketplace/MarketplacePagination';

interface MarketplaceViewProps {
  initialCategory?: string;
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

const SearchIcon: React.FC = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.35-4.35" />
  </svg>
);

const POPULAR_CROPS = ['Onion', 'Potato', 'Tomato', 'Wheat', 'Pomegranate', 'Soybean'];

const CATEGORY_LABELS: Record<string, string> = {
  vegetables: 'Vegetables',
  fruits: 'Fruits',
  grains: 'Grains',
  pulses: 'Pulses',
  spices: 'Spices',
  other_crops: 'Commercial Crops',
};

const PAGE_SIZE = 12;

export const MarketplaceView: React.FC<MarketplaceViewProps> = ({ initialCategory, onNavigate }) => {
  const { user, isAuthenticated } = useAuth();
  const [lots, setLots] = useState<ProduceLotSummary[]>([]);
  const [commodities, setCommodities] = useState<Commodity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Filter State
  const [category, setCategory] = useState<string>(initialCategory || '');
  const [commodityId, setCommodityId] = useState<string>('');
  const [search, setSearch] = useState<string>('');
  const [stateFilter, setStateFilter] = useState<string>('');
  const [districtFilter, setDistrictFilter] = useState<string>('');
  const [minPrice, setMinPrice] = useState<string>('');
  const [maxPrice, setMaxPrice] = useState<string>('');
  const [minQuantity, setMinQuantity] = useState<string>('');
  const [sellerRole, setSellerRole] = useState<string>('');
  const [qualityGrade, setQualityGrade] = useState<string>('');

  // Sorting State
  const [sortBy, setSortBy] = useState<SortOptionId>('recommended');

  // Pagination State
  const [page, setPage] = useState<number>(1);
  const [total, setTotal] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);

  useEffect(() => {
    let mounted = true;
    const init = async () => {
      try {
        const list = await api.getCommodities();
        if (mounted) setCommodities(list);
      } catch (err) {
        console.error('Failed to load commodities:', err);
      }
    };
    void init();
    return () => {
      mounted = false;
    };
  }, []);

  // Helper handlers that update filter/sort criteria and reset to page 1
  const updateCategory = (val: string) => { setCategory(val); setPage(1); };
  const updateCommodityId = (val: string) => { setCommodityId(val); setPage(1); };
  const updateStateFilter = (val: string) => { setStateFilter(val); setPage(1); };
  const updateDistrictFilter = (val: string) => { setDistrictFilter(val); setPage(1); };
  const updateMinPrice = (val: string) => { setMinPrice(val); setPage(1); };
  const updateMaxPrice = (val: string) => { setMaxPrice(val); setPage(1); };
  const updateMinQuantity = (val: string) => { setMinQuantity(val); setPage(1); };
  const updateSellerRole = (val: string) => { setSellerRole(val); setPage(1); };
  const updateQualityGrade = (val: string) => { setQualityGrade(val); setPage(1); };
  const updateSortBy = (val: SortOptionId) => { setSortBy(val); setPage(1); };

  const fetchLots = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await api.browseMarketplace({
        category: category || undefined,
        commodity_id: commodityId || undefined,
        search: search.trim() || undefined,
        state: stateFilter || undefined,
        district: districtFilter || undefined,
        min_price: minPrice ? Number(minPrice) : undefined,
        max_price: maxPrice ? Number(maxPrice) : undefined,
        min_quantity: minQuantity ? Number(minQuantity) : undefined,
        seller_role: sellerRole || undefined,
        quality_grade: qualityGrade || undefined,
        sort_by: sortBy,
        page,
        page_size: PAGE_SIZE,
      });
      const items = results && Array.isArray(results.items) ? results.items : (Array.isArray(results) ? (results as unknown as ProduceLotSummary[]) : []);
      const totalCount = results && typeof results.total === 'number' ? results.total : items.length;
      const pagesCount = results && typeof results.total_pages === 'number' ? results.total_pages : Math.max(1, Math.ceil(items.length / PAGE_SIZE));
      setLots(items);
      setTotal(totalCount);
      setTotalPages(pagesCount);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load produce listings.');
    } finally {
      setLoading(false);
    }
  }, [category, commodityId, search, stateFilter, districtFilter, minPrice, maxPrice, minQuantity, sellerRole, qualityGrade, sortBy, page]);

  useEffect(() => {
    let active = true;
    const run = async () => {
      if (active) {
        await fetchLots();
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [fetchLots]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchLots();
  };

  const handleClearSearch = () => {
    setSearch('');
    setPage(1);
  };

  const handlePopularClick = (crop: string) => {
    const next = search.trim().toLowerCase() === crop.toLowerCase() ? '' : crop;
    setSearch(next);
    setPage(1);
  };

  const handleResetFilters = () => {
    setCategory('');
    setCommodityId('');
    setStateFilter('');
    setDistrictFilter('');
    setMinPrice('');
    setMaxPrice('');
    setMinQuantity('');
    setSellerRole('');
    setQualityGrade('');
    setPage(1);
  };

  const handleResetAll = () => {
    setSearch('');
    handleResetFilters();
  };

  const selectedCommodity = commodities.find((c) => c.id === commodityId);
  const isFarmerOrFPO = user?.roles.includes('farmer') || user?.roles.includes('fpo');
  const isBuyer = user?.roles.includes('buyer');
  const isTransporter = user?.roles.includes('transporter');

  return (
    <div className="marketplace-page section-container">
      {/* Step 3.1: Marketplace Shell & Header */}
      <div className="marketplace-header-shell">
        <div className="marketplace-title-group">
          <h1 className="marketplace-page-title">Live Produce Marketplace</h1>
          <p className="marketplace-page-subtitle">
            Direct farm-gate agricultural trade across producers and buyers.
          </p>
        </div>

        <div className="marketplace-header-actions">
          {isAuthenticated && isFarmerOrFPO && (
            <button className="btn-primary" onClick={() => onNavigate('create-lot')}>
              + List Produce
            </button>
          )}

          {!isAuthenticated && (
            <button className="btn-outline" onClick={() => onNavigate('register', { role: 'farmer' })}>
              Sell Produce
            </button>
          )}

          {/* Buyers and Transporters do not see produce-listing buttons */}
          {isAuthenticated && (isBuyer || isTransporter) && null}
        </div>
      </div>

      {/* Step 3.2: Marketplace Primary Search */}
      <div className="marketplace-search-section">
        <form onSubmit={handleSearchSubmit} className="marketplace-search-bar" role="search">
          <div className="marketplace-search-wrapper">
            <span className="marketplace-search-icon">
              <SearchIcon />
            </span>
            <input
              type="text"
              aria-label="Search crops, varieties, districts, markets or lots"
              placeholder="Search crops, varieties, districts, markets or lots..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="marketplace-search-input"
            />
            {search.trim().length > 0 && (
              <button
                type="button"
                className="marketplace-search-clear-btn"
                onClick={handleClearSearch}
                aria-label="Clear search"
                title="Clear search"
              >
                ✕
              </button>
            )}
          </div>
          <button type="submit" className="btn-primary marketplace-search-submit-btn">
            Search
          </button>
        </form>

        {/* Popular Search Shortcuts */}
        <div className="popular-shortcuts-row">
          <span className="popular-shortcuts-label">Popular:</span>
          {POPULAR_CROPS.map((crop) => (
            <button
              key={crop}
              type="button"
              className={`popular-shortcut-chip ${search.trim().toLowerCase() === crop.toLowerCase() ? 'active' : ''}`}
              onClick={() => handlePopularClick(crop)}
            >
              {crop}
            </button>
          ))}
        </div>
      </div>

      {/* Step 3.3: Compact Marketplace Filter Bar */}
      <MarketplaceFilterBar
        category={category}
        setCategory={updateCategory}
        stateFilter={stateFilter}
        setStateFilter={updateStateFilter}
        districtFilter={districtFilter}
        setDistrictFilter={updateDistrictFilter}
        qualityGrade={qualityGrade}
        setQualityGrade={updateQualityGrade}
        minPrice={minPrice}
        setMinPrice={updateMinPrice}
        maxPrice={maxPrice}
        setMaxPrice={updateMaxPrice}
        minQuantity={minQuantity}
        setMinQuantity={updateMinQuantity}
        sellerRole={sellerRole}
        setSellerRole={updateSellerRole}
        commodityId={commodityId}
        setCommodityId={updateCommodityId}
        commodities={commodities}
        onResetFilters={handleResetFilters}
      />

      {/* Active Filter Chips */}
      <ActiveFilterChips
        category={category}
        categoryLabel={category ? CATEGORY_LABELS[category] || category : undefined}
        commodityName={selectedCommodity?.name}
        stateFilter={stateFilter}
        districtFilter={districtFilter}
        qualityGrade={qualityGrade}
        minPrice={minPrice}
        maxPrice={maxPrice}
        minQuantity={minQuantity}
        sellerRole={sellerRole}
        onRemoveCategory={() => updateCategory('')}
        onRemoveCommodity={() => updateCommodityId('')}
        onRemoveState={() => updateStateFilter('')}
        onRemoveDistrict={() => updateDistrictFilter('')}
        onRemoveQualityGrade={() => updateQualityGrade('')}
        onRemoveMinPrice={() => updateMinPrice('')}
        onRemoveMaxPrice={() => updateMaxPrice('')}
        onRemoveMinQuantity={() => updateMinQuantity('')}
        onRemoveSellerRole={() => updateSellerRole('')}
        onResetAll={handleResetAll}
      />

      {/* Results Header & Sort Control */}
      <div className="marketplace-results-header">
        <span className="marketplace-results-count">
          {total} {total === 1 ? 'produce lot' : 'produce lots'}
        </span>
        <MarketplaceSortControl value={sortBy} onChange={updateSortBy} />
      </div>

      {/* Produce Lots Results Grid */}
      {error && <div className="alert-box alert-error">{error}</div>}

      {loading ? (
        <div className="produce-lots-grid" aria-label="Loading produce listings">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div key={n} className="produce-card-skeleton">
              <div className="skeleton-header" />
              <div className="skeleton-title" />
              <div className="skeleton-subtitle" />
              <div className="skeleton-metric-box" />
              <div className="skeleton-meta" />
              <div className="skeleton-footer" />
            </div>
          ))}
        </div>
      ) : lots.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🌾</div>
          <h3>No Produce Listings Found</h3>
          <p>Try adjusting your search filters or browse all agricultural categories.</p>
          <button className="btn-secondary" onClick={handleResetAll}>
            Reset All Filters
          </button>
        </div>
      ) : (
        <>
          <div className="produce-lots-grid" role="region" aria-label="Marketplace produce listings">
            {lots.map((lot) => (
              <ProduceLotCard
                key={lot.id}
                lot={lot}
                onViewLot={(lotId) => onNavigate('produce-detail', { lotId })}
              />
            ))}
          </div>

          <MarketplacePagination
            currentPage={page}
            totalPages={totalPages}
            totalItems={total}
            pageSize={PAGE_SIZE}
            onPageChange={(newPage) => {
              setPage(newPage);
              window.scrollTo({ top: 300, behavior: 'smooth' });
            }}
            disabled={loading}
          />
        </>
      )}
    </div>
  );
};
