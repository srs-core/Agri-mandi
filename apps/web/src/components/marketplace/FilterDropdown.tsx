import React, { useEffect, useRef } from 'react';

interface FilterDropdownProps {
  label: string;
  activeSummary?: string;
  isActive?: boolean;
  isOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
  children: React.ReactNode;
  align?: 'left' | 'right';
  className?: string;
}

export const FilterDropdown: React.FC<FilterDropdownProps> = ({
  label,
  activeSummary,
  isActive = false,
  isOpen,
  onToggle,
  onClose,
  children,
  align = 'left',
  className = '',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        onClose();
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  return (
    <div ref={containerRef} className={`filter-dropdown-wrapper ${className}`}>
      <button
        type="button"
        className={`filter-dropdown-trigger ${isActive ? 'is-active' : ''} ${isOpen ? 'is-open' : ''}`}
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
      >
        <span className="filter-trigger-label">
          {label}
          {activeSummary && <span className="filter-trigger-summary">: {activeSummary}</span>}
        </span>
        <span className="filter-trigger-caret" aria-hidden="true">
          {isOpen ? '▴' : '▾'}
        </span>
      </button>

      {isOpen && (
        <div
          className={`filter-dropdown-popover ${align === 'right' ? 'align-right' : 'align-left'}`}
          role="dialog"
          aria-label={`${label} filter`}
        >
          {children}
        </div>
      )}
    </div>
  );
};
