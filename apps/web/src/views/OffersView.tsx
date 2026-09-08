import React, { useEffect, useState } from 'react';
import { api, type Offer } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface OffersViewProps {
  initialLotId?: string;
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const OffersView: React.FC<OffersViewProps> = ({ initialLotId, onNavigate }) => {
  const { user } = useAuth();
  const isSeller = user?.roles.includes('farmer') || user?.roles.includes('fpo');
  const [tab, setTab] = useState<'received' | 'sent'>(isSeller ? 'received' : 'sent');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Expanded negotiation history per offer
  const [expandedHistory, setExpandedHistory] = useState<Record<string, boolean>>({});

  // Counter offer modal state
  const [counterModalOffer, setCounterModalOffer] = useState<Offer | null>(null);
  const [counterPrice, setCounterPrice] = useState<string>('');
  const [counterQty, setCounterQty] = useState<string>('');
  const [counterNotes, setCounterNotes] = useState<string>('');
  const [submittingCounter, setSubmittingCounter] = useState(false);

  const fetchOffers = React.useCallback(async () => {
    try {
      const data = await api.getOffers({
        role_perspective: tab,
        status: statusFilter || undefined,
        lot_id: initialLotId || undefined,
      });
      setOffers(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load commercial offers.');
    } finally {
      setLoading(false);
    }
  }, [tab, statusFilter, initialLotId]);

  useEffect(() => {
    let active = true;
    const run = async () => {
      if (active) {
        await fetchOffers();
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [fetchOffers]);

  const toggleHistory = (offerId: string) => {
    setExpandedHistory((prev) => ({ ...prev, [offerId]: !prev[offerId] }));
  };

  const handleAccept = async (offerId: string) => {
    setActionLoading(offerId);
    setError(null);
    setSuccessMsg(null);
    try {
      const order = await api.acceptOffer(offerId);
      setSuccessMsg(`Offer accepted! Order #${order.id.slice(0, 8)} confirmed.`);
      await fetchOffers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to accept offer.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (offerId: string) => {
    setActionLoading(offerId);
    setError(null);
    setSuccessMsg(null);
    try {
      await api.rejectOffer(offerId);
      setSuccessMsg('Proposal declined.');
      await fetchOffers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to decline proposal.');
    } finally {
      setActionLoading(null);
    }
  };

  const handleWithdraw = async (offerId: string) => {
    setActionLoading(offerId);
    setError(null);
    setSuccessMsg(null);
    try {
      await api.withdrawOffer(offerId);
      setSuccessMsg('Proposal withdrawn.');
      await fetchOffers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to withdraw proposal.');
    } finally {
      setActionLoading(null);
    }
  };

  const openCounterModal = (offer: Offer) => {
    setCounterModalOffer(offer);
    const activePrice = offer.current_price_per_unit || offer.offered_price_per_unit;
    const activeQty = offer.current_quantity || offer.offered_quantity;
    setCounterPrice(String(activePrice));
    setCounterQty(String(activeQty));
    setCounterNotes('');
    setError(null);
  };

  const closeCounterModal = () => {
    setCounterModalOffer(null);
    setCounterPrice('');
    setCounterQty('');
    setCounterNotes('');
  };

  const submitCounterOffer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!counterModalOffer) return;
    const priceNum = Number(counterPrice);
    const qtyNum = Number(counterQty);
    if (isNaN(priceNum) || priceNum <= 0) {
      setError('Please enter a valid counter rate per unit greater than 0.');
      return;
    }
    if (isNaN(qtyNum) || qtyNum <= 0) {
      setError('Please enter a valid quantity greater than 0.');
      return;
    }

    setSubmittingCounter(true);
    setError(null);
    try {
      await api.counterOffer(counterModalOffer.id, {
        price_per_unit: priceNum,
        quantity: qtyNum,
        notes: counterNotes.trim() || undefined,
      });
      setSuccessMsg(`Counter-offer of ₹${priceNum.toLocaleString('en-IN')}/${counterModalOffer.unit} submitted successfully.`);
      closeCounterModal();
      await fetchOffers();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit counter-offer.');
    } finally {
      setSubmittingCounter(false);
    }
  };

  return (
    <div className="offers-page section-container">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Commercial Trade Offers & Negotiations</h1>
          <p className="page-subtitle">
            Manage binding purchase bids, bilateral price counter-proposals, and verified contract confirmations.
          </p>
        </div>
      </div>

      {error && <div className="alert-box alert-error">{error}</div>}
      {successMsg && <div className="alert-box alert-success">{successMsg}</div>}

      {/* Tabs */}
      <div className="tabs-header-row">
        <div className="tab-buttons">
          <button
            className={`tab-btn ${tab === 'received' ? 'active' : ''}`}
            onClick={() => setTab('received')}
          >
            📥 Received Offers (As Seller)
          </button>
          <button
            className={`tab-btn ${tab === 'sent' ? 'active' : ''}`}
            onClick={() => setTab('sent')}
          >
            📤 Sent Offers (As Buyer)
          </button>
        </div>

        <div className="filter-select-wrapper">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="form-select"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="countered">Countered</option>
            <option value="accepted">Accepted</option>
            <option value="declined">Declined</option>
            <option value="withdrawn">Withdrawn</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="loading-spinner">Loading offers...</div>
      ) : offers.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">🤝</div>
          <h3>No Offers Found</h3>
          <p>
            {tab === 'received'
              ? 'You have not received any commercial offers on your produce lots yet.'
              : 'You have not sent any offers to produce sellers yet.'}
          </p>
          <button className="btn-primary" onClick={() => onNavigate('marketplace')}>
            Browse Live Marketplace
          </button>
        </div>
      ) : (
        <div className="offers-table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Produce Lot / Crop</th>
                <th>{tab === 'received' ? 'Buyer' : 'Seller'}</th>
                <th>Quantity</th>
                <th>Current Proposed Rate</th>
                <th>Total Deal Value</th>
                <th>Status & Turn</th>
                <th>Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {offers.map((offer) => {
                const currentPrice = offer.current_price_per_unit ?? offer.offered_price_per_unit;
                const currentQty = offer.current_quantity ?? offer.offered_quantity;
                const totalVal = currentQty * currentPrice;
                const isNegotiable = offer.price_mode === 'NEGOTIABLE';

                // Robust turn detection: checks response_required_from_user_id, with role/perspective fallback
                const isMyTurn = (offer.status === 'pending' || offer.status === 'countered') && (
                  (offer.response_required_from_user_id && offer.response_required_from_user_id === user?.id) ||
                  (!offer.response_required_from_user_id && (
                    (tab === 'received' && offer.status === 'pending') ||
                    (tab === 'sent' && offer.status === 'countered')
                  ))
                );

                const isMyProposal = (offer.status === 'pending' || offer.status === 'countered') && (
                  (offer.current_proposer_user_id && offer.current_proposer_user_id === user?.id) ||
                  (!offer.current_proposer_user_id && (
                    (tab === 'sent' && offer.status === 'pending') ||
                    (tab === 'received' && offer.status === 'countered')
                  ))
                );

                const isExpanded = !!expandedHistory[offer.id];

                return (
                  <React.Fragment key={offer.id}>
                    <tr>
                      <td>
                        <div className="lot-name-link" onClick={() => onNavigate('produce-detail', { lotId: offer.produce_lot_id })}>
                          {offer.produce_title}
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.25rem' }}>
                          <span className="subtext">{offer.commodity_name}</span>
                          <span className={`price-mode-pill ${isNegotiable ? 'price-mode-negotiable' : 'price-mode-fixed'}`}>
                            {isNegotiable ? '🤝 Negotiable' : '🏷️ Fixed Price'}
                          </span>
                        </div>
                      </td>
                      <td>
                        <strong>{tab === 'received' ? offer.buyer_name : offer.seller_name}</strong>
                      </td>
                      <td>
                        {currentQty} {offer.unit}
                      </td>
                      <td className="price-text">
                        ₹{currentPrice.toLocaleString('en-IN')}/{offer.unit}
                        {offer.status === 'countered' && (
                          <div style={{ fontSize: '0.75rem', color: '#d97706', fontWeight: 600 }}>
                            Countered
                          </div>
                        )}
                      </td>
                      <td className="deal-total-text">
                        ₹{totalVal.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                      </td>
                      <td>
                        <div>
                          <span className={`status-pill status-${offer.status}`}>
                            {offer.status.toUpperCase()}
                          </span>
                        </div>
                        {isMyTurn && (
                          <div className="turn-badge turn-action-required">
                            ⚡ Your Response Required
                          </div>
                        )}
                        {isMyProposal && (
                          <div className="turn-badge turn-waiting">
                            ⏳ Awaiting {tab === 'received' ? 'Buyer' : 'Seller'} Response
                          </div>
                        )}
                      </td>
                      <td className="subtext">
                        {new Date(offer.created_at).toLocaleDateString()}
                        {offer.history && offer.history.length > 0 && (
                          <button
                            type="button"
                            className="btn-history-toggle"
                            onClick={() => toggleHistory(offer.id)}
                            title="Toggle negotiation history timeline"
                          >
                            📜 {offer.history.length} {offer.history.length === 1 ? 'proposal' : 'proposals'} {isExpanded ? '▲' : '▼'}
                          </button>
                        )}
                      </td>
                      <td>
                        {isMyTurn && (
                          <div className="action-btn-group" style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                            <div style={{ display: 'flex', gap: '0.35rem' }}>
                              <button
                                className="btn-success-sm"
                                onClick={() => handleAccept(offer.id)}
                                disabled={actionLoading === offer.id}
                              >
                                {actionLoading === offer.id ? '...' : `✓ Accept ₹${currentPrice.toLocaleString('en-IN')}`}
                              </button>
                              <button
                                className="btn-danger-sm"
                                onClick={() => handleReject(offer.id)}
                                disabled={actionLoading === offer.id}
                              >
                                {actionLoading === offer.id ? '...' : '✕ Decline'}
                              </button>
                            </div>
                            {isNegotiable && (
                              <button
                                className="btn-counter-sm"
                                onClick={() => openCounterModal(offer)}
                                disabled={actionLoading === offer.id}
                              >
                                💬 Counter Offer
                              </button>
                            )}
                          </div>
                        )}

                        {isMyProposal && (
                          <button
                            className="btn-secondary btn-sm"
                            onClick={() => handleWithdraw(offer.id)}
                            disabled={actionLoading === offer.id}
                          >
                            {actionLoading === offer.id ? '...' : 'Withdraw'}
                          </button>
                        )}

                        {offer.status === 'accepted' && (
                          <button
                            className="btn-secondary btn-sm"
                            onClick={() => onNavigate('orders')}
                          >
                            View Order ➔
                          </button>
                        )}
                      </td>
                    </tr>

                    {/* Expandable Negotiation Timeline */}
                    {isExpanded && offer.history && offer.history.length > 0 && (
                      <tr>
                        <td colSpan={8} style={{ padding: '0 1rem 1.25rem 1rem', background: '#f8fafc' }}>
                          <div className="negotiation-history-card">
                            <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: '#334155', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <span>📜 Negotiation History & Proposal Timeline</span>
                              <span style={{ fontSize: '0.75rem', fontWeight: 400, color: '#64748b' }}>
                                ({offer.history.length} total rounds)
                              </span>
                            </h4>
                            <div className="negotiation-timeline">
                              {offer.history.map((proposal, idx) => (
                                <div
                                  key={proposal.id}
                                  className={`timeline-step ${proposal.proposer_role === 'seller' || proposal.proposer_role === 'farmer' ? 'step-farmer' : 'step-buyer'}`}
                                >
                                  <div className="timeline-step-header">
                                    <div className="step-actor">
                                      <span>Round {idx + 1}: {proposal.proposer_name}</span>
                                      <span className={`actor-badge ${proposal.proposer_role === 'seller' || proposal.proposer_role === 'farmer' ? 'actor-badge-farmer' : 'actor-badge-buyer'}`}>
                                        {proposal.proposer_role === 'seller' || proposal.proposer_role === 'farmer' ? 'Farmer / Seller' : 'Buyer'}
                                      </span>
                                      <span className={`status-pill status-${proposal.status_at_step}`} style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem' }}>
                                        {proposal.status_at_step.toUpperCase()}
                                      </span>
                                    </div>
                                    <span className="step-date">
                                      {new Date(proposal.created_at).toLocaleString()}
                                    </span>
                                  </div>
                                  <div className="step-details">
                                    <span>
                                      <strong>Rate:</strong> ₹{proposal.price_per_unit.toLocaleString('en-IN')}/{offer.unit}
                                    </span>
                                    <span>
                                      <strong>Quantity:</strong> {proposal.quantity} {offer.unit}
                                    </span>
                                    <span>
                                      <strong>Value:</strong> ₹{proposal.total_amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                                    </span>
                                  </div>
                                  {proposal.notes && (
                                    <div className="step-note">
                                      💬 "{proposal.notes}"
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Counter Offer Modal */}
      {counterModalOffer && (
        <div className="modal-overlay" onClick={closeCounterModal}>
          <div className="counter-modal" onClick={(e) => e.stopPropagation()}>
            <div className="counter-modal-header">
              <h3>Submit Counter-Offer</h3>
              <button className="close-modal-btn" onClick={closeCounterModal}>&times;</button>
            </div>

            <div style={{ background: '#f8fafc', padding: '0.75rem', borderRadius: '6px', marginBottom: '1rem', border: '1px solid #e2e8f0' }}>
              <div style={{ fontWeight: 600, color: '#1e293b' }}>{counterModalOffer.produce_title}</div>
              <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
                Current Rate: ₹{(counterModalOffer.current_price_per_unit ?? counterModalOffer.offered_price_per_unit).toLocaleString('en-IN')}/{counterModalOffer.unit}
              </div>
            </div>

            <form onSubmit={submitCounterOffer}>
              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">
                  Your Counter Rate (₹ per {counterModalOffer.unit}) <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="1"
                  className="form-input"
                  value={counterPrice}
                  onChange={(e) => setCounterPrice(e.target.value)}
                  placeholder="e.g. 1750"
                  required
                />
              </div>

              <div className="form-group" style={{ marginBottom: '1rem' }}>
                <label className="form-label">
                  Quantity ({counterModalOffer.unit}) <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <input
                  type="number"
                  step="0.001"
                  min="0.001"
                  className="form-input"
                  value={counterQty}
                  onChange={(e) => setCounterQty(e.target.value)}
                  placeholder="e.g. 30"
                  required
                />
              </div>

              {Number(counterPrice) > 0 && Number(counterQty) > 0 && (
                <div style={{ background: '#ecfdf5', padding: '0.75rem', borderRadius: '6px', marginBottom: '1rem', border: '1px solid #a7f3d0' }}>
                  <div style={{ fontSize: '0.8rem', color: '#065f46' }}>Total Counter Value:</div>
                  <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#047857' }}>
                    ₹{(Number(counterPrice) * Number(counterQty)).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                  </div>
                </div>
              )}

              <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                <label className="form-label">
                  Negotiation Notes / Remarks (Optional)
                </label>
                <textarea
                  className="form-textarea"
                  rows={3}
                  value={counterNotes}
                  onChange={(e) => setCounterNotes(e.target.value)}
                  placeholder="e.g. Quality is Grade A Jyoti, ₹1750 is fair rate."
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={closeCounterModal}
                  disabled={submittingCounter}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={submittingCounter}
                >
                  {submittingCounter ? 'Submitting...' : 'Submit Counter Offer ➔'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
