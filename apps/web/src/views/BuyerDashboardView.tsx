import React, { useEffect, useState } from 'react';
import { api, type BuyerRequirement, type Offer, type Order } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface BuyerDashboardViewProps {
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const BuyerDashboardView: React.FC<BuyerDashboardViewProps> = ({ onNavigate }) => {
  const { user, profile } = useAuth();
  const [myRequirements, setMyRequirements] = useState<BuyerRequirement[]>([]);
  const [sentOffers, setSentOffers] = useState<Offer[]>([]);
  const [myOrders, setMyOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const [reqs, offers, orders] = await Promise.all([
          api.getMyBuyerRequirements(),
          api.getOffers({ role_perspective: 'sent' }),
          api.getOrders(),
        ]);
        setMyRequirements(reqs);
        setSentOffers(offers);
        setMyOrders(orders);
      } catch (err) {
        console.error('Failed to load buyer dashboard:', err);
      } finally {
        setLoading(false);
      }
    };
    loadDashboard();
  }, []);

  const totalSpent = myOrders
    .filter((o) => o.status !== 'cancelled')
    .reduce((acc, o) => acc + o.total_amount, 0);

  return (
    <div className="dashboard-page section-container">
      {/* Welcome Banner */}
      <div className="dashboard-welcome-card">
        <div className="welcome-content">
          <div className="welcome-avatar">🏭</div>
          <div>
            <h1 className="welcome-title">Buyer Procurement Desk • {user?.display_name}</h1>
            <p className="welcome-sub">
              Organization: {profile?.organization_name || user?.display_name} • GSTIN:{' '}
              {profile?.gstin || 'Not registered'}
            </p>
          </div>
        </div>

        <div className="welcome-actions">
          <button className="btn-primary" onClick={() => onNavigate('create-requirement')}>
            + Post Procurement Demand
          </button>
          <button className="btn-secondary" onClick={() => onNavigate('marketplace')}>
            Browse Produce
          </button>
        </div>
      </div>

      {/* KPI Stats */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Active Demands</span>
          <span className="kpi-value">{myRequirements.filter((r) => r.status === 'active').length}</span>
          <span className="kpi-sub">Total {myRequirements.length} posted</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Sent Trade Offers</span>
          <span className="kpi-value">{sentOffers.length}</span>
          <span className="kpi-sub">{sentOffers.filter((o) => o.status === 'pending').length} pending</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Active Contracts</span>
          <span className="kpi-value">{myOrders.filter((o) => o.status !== 'cancelled').length}</span>
          <span className="kpi-sub">Confirmed & in-transit</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Procured Volume Value</span>
          <span className="kpi-value price-text">₹{totalSpent.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
          <span className="kpi-sub">Total contract GMV</span>
        </div>
      </div>

      {/* My Requirements Table */}
      <div className="card dashboard-table-card">
        <div className="table-card-header">
          <h2>My Active Procurement Demands ({myRequirements.length})</h2>
          <button className="btn-link" onClick={() => onNavigate('create-requirement')}>
            + Post Another Demand
          </button>
        </div>

        {loading ? (
          <div className="loading-spinner">Loading requirements...</div>
        ) : myRequirements.length === 0 ? (
          <div className="empty-state-sm">
            <p>You haven't posted any procurement demands yet.</p>
            <button className="btn-primary btn-sm" onClick={() => onNavigate('create-requirement')}>
              + Post First Demand
            </button>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Crop Commodity</th>
                <th>Required Quantity</th>
                <th>Target Price</th>
                <th>Min Grade</th>
                <th>Target Date</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {myRequirements.map((req) => (
                <tr key={req.id}>
                  <td>
                    <strong>{req.commodity_name}</strong>
                  </td>
                  <td>
                    {req.required_quantity} {req.unit}
                  </td>
                  <td>
                    {req.target_price_per_unit ? `₹${req.target_price_per_unit.toLocaleString('en-IN')}/${req.unit}` : 'Flexible'}
                  </td>
                  <td>
                    <span className="grade-badge">{req.minimum_quality_grade || 'Standard'}</span>
                  </td>
                  <td className="subtext">{req.delivery_by ? new Date(req.delivery_by).toLocaleDateString() : 'N/A'}</td>
                  <td>
                    <span className={`status-pill status-${req.status}`}>{req.status.toUpperCase()}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Recent Sent Offers */}
      <div className="card dashboard-table-card">
        <div className="table-card-header">
          <h2>My Recent Commercial Bids ({sentOffers.length})</h2>
          <button className="btn-link" onClick={() => onNavigate('offers')}>
            View All Sent Offers ➔
          </button>
        </div>

        {sentOffers.length === 0 ? (
          <div className="empty-state-sm">
            <p>You haven't placed any offers on produce lots yet.</p>
            <button className="btn-primary btn-sm" onClick={() => onNavigate('marketplace')}>
              Browse Marketplace & Bid
            </button>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Produce Lot</th>
                <th>Producer</th>
                <th>Offered Qty</th>
                <th>Offered Rate</th>
                <th>Total Value</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {sentOffers.slice(0, 5).map((offer) => (
                <tr key={offer.id}>
                  <td>
                    <strong>{offer.produce_title}</strong>
                  </td>
                  <td>{offer.seller_name}</td>
                  <td>{offer.offered_quantity} {offer.unit}</td>
                  <td>₹{offer.offered_price_per_unit.toLocaleString('en-IN')}/{offer.unit}</td>
                  <td className="deal-total-text">₹{offer.total_amount.toLocaleString('en-IN')}</td>
                  <td>
                    <span className={`status-pill status-${offer.status}`}>{offer.status.toUpperCase()}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
