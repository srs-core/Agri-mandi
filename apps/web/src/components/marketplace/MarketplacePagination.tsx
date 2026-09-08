import React from 'react';

export interface MarketplacePaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (newPage: number) => void;
  disabled?: boolean;
}

const getPageNumbers = (currentPage: number, totalPages: number): (number | 'ellipsis')[] => {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5, 'ellipsis', totalPages];
  }

  if (currentPage >= totalPages - 3) {
    return [1, 'ellipsis', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
  }

  return [1, 'ellipsis', currentPage - 1, currentPage, currentPage + 1, 'ellipsis', totalPages];
};

export const MarketplacePagination: React.FC<MarketplacePaginationProps> = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  disabled = false,
}) => {
  if (totalPages <= 1 || totalItems === 0) {
    return null;
  }

  const pages = getPageNumbers(currentPage, totalPages);
  const isFirstPage = currentPage <= 1;
  const isLastPage = currentPage >= totalPages;

  const handlePrev = () => {
    if (!isFirstPage && !disabled) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (!isLastPage && !disabled) {
      onPageChange(currentPage + 1);
    }
  };

  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalItems);

  return (
    <nav
      className="marketplace-pagination-nav"
      aria-label="Produce lots pagination"
      role="navigation"
    >
      <div className="marketplace-pagination-info">
        Showing <span className="pagination-range-text">{startItem}–{endItem}</span> of <span className="pagination-total-text">{totalItems}</span> listings
      </div>

      <div className="marketplace-pagination-controls">
        {/* Previous Button */}
        <button
          type="button"
          className="pagination-btn pagination-nav-btn"
          onClick={handlePrev}
          disabled={isFirstPage || disabled}
          aria-label="Go to previous page"
        >
          <span aria-hidden="true">‹</span>
          <span className="pagination-btn-label">Prev</span>
        </button>

        {/* Desktop Page Numbers */}
        <div className="pagination-pages-group">
          {pages.map((p, idx) => {
            if (p === 'ellipsis') {
              return (
                <span
                  key={`ellipsis-${idx}`}
                  className="pagination-ellipsis"
                  aria-hidden="true"
                >
                  …
                </span>
              );
            }

            const isActive = p === currentPage;
            return (
              <button
                key={p}
                type="button"
                className={`pagination-btn pagination-page-btn ${isActive ? 'is-active' : ''}`}
                onClick={() => !isActive && !disabled && onPageChange(p)}
                disabled={disabled}
                aria-label={`Go to page ${p}`}
                aria-current={isActive ? 'page' : undefined}
              >
                {p}
              </button>
            );
          })}
        </div>

        {/* Mobile Page Status Badge */}
        <div className="pagination-mobile-indicator" aria-hidden="true">
          Page {currentPage} of {totalPages}
        </div>

        {/* Next Button */}
        <button
          type="button"
          className="pagination-btn pagination-nav-btn"
          onClick={handleNext}
          disabled={isLastPage || disabled}
          aria-label="Go to next page"
        >
          <span className="pagination-btn-label">Next</span>
          <span aria-hidden="true">›</span>
        </button>
      </div>
    </nav>
  );
};
