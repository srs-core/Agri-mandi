import React, { useEffect, useRef, useState } from 'react';

export type SortOptionId =
  | 'recommended'
  | 'price_asc'
  | 'price_desc'
  | 'newest'
  | 'qty_desc'
  | 'qty_asc';

export interface SortOption {
  id: SortOptionId;
  label: string;
}

const SORT_OPTIONS: SortOption[] = [
  { id: 'recommended', label: 'Recommended' },
  { id: 'price_asc', label: 'Price: Low to High' },
  { id: 'price_desc', label: 'Price: High to Low' },
  { id: 'newest', label: 'Newest' },
  { id: 'qty_desc', label: 'Quantity: High to Low' },
  { id: 'qty_asc', label: 'Quantity: Low to High' },
];

export interface MarketplaceSortControlProps {
  value: SortOptionId;
  onChange: (sortId: SortOptionId) => void;
}

export const MarketplaceSortControl: React.FC<MarketplaceSortControlProps> = ({
  value,
  onChange,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const selectedOption = SORT_OPTIONS.find((opt) => opt.id === value) || SORT_OPTIONS[0];

  const handleSelect = (optId: SortOptionId) => {
    onChange(optId);
    setIsOpen(false);
  };

  return (
    <div ref={containerRef} className="marketplace-sort-wrapper">
      <button
        type="button"
        className={`marketplace-sort-trigger ${isOpen ? 'is-open' : ''} ${value !== 'recommended' ? 'is-sorted' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={`Sort listings: currently ${selectedOption.label}`}
      >
        <span className="sort-label-prefix">Sort:</span>
        <span className="sort-label-value">{selectedOption.label}</span>
        <span className="sort-caret" aria-hidden="true">
          {isOpen ? '▴' : '▾'}
        </span>
      </button>

      {isOpen && (
        <div className="marketplace-sort-popover" role="listbox" aria-label="Sort options">
          {SORT_OPTIONS.map((opt) => {
            const isSelected = opt.id === value;
            return (
              <button
                key={opt.id}
                type="button"
                role="option"
                aria-selected={isSelected}
                className={`sort-menu-item ${isSelected ? 'is-selected' : ''}`}
                onClick={() => handleSelect(opt.id)}
              >
                <span className="sort-item-check">{isSelected ? '✓' : ''}</span>
                <span className="sort-item-text">{opt.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
