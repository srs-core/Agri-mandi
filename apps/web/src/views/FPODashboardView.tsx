import React, { useEffect, useState } from 'react';
import { api, type BuyerRequirement, type Offer, type Order, type ProduceLotSummary } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface FPODashboardViewProps {
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const FPODashboardView: React.FC<FPODashboardViewProps> = ({ onNavigate }) => {
  const { user, profile } = useAuth();
  const [lots, setLots] = useState<ProduceLotSummary[]>([]);
  const [buyerDemands, setBuyerDemands] = useState<BuyerRequirement[]>([]);
  const [incomingOffers, setIncomingOffers] = useState<Offer[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadFPOData = async () => {
      try {
        const [myLots, demands, offers, myOrders] = await Promise.all([
          api.getMyProduceLots(),
          api.browseBuyerRequirements(),
          api.getOffers({ role_perspective: 'received', status: 'pending' }),
          api.getOrders(),
        ]);
        setLots(myLots);
        setBuyerDemands(demands);
        setIncomingOffers(offers);
        setOrders(myOrders);
      } catch (err) {
        console.error('Failed to load FPO data:', err);
      } finally {
        setLoading(false);
      }
    };
    loadFPOData();
  }, []);

  const aggregatedLots = lots.filter((l) => l.is_aggregated);
  const totalOrdersAmount = orders
    .filter((o) => o.status !== 'cancelled')
    .reduce((acc, o) => acc + o.total_amount, 0);

  return (
    <div className="dashboard-page section-container">
      {/* FPO Welcome Header */}
      <div className="dashboard-welcome-card">
        <div className="welcome-content">
          <div className="welcome-avatar">🏢</div>
          <div>
            <h1 className="welcome-title">FPO Enterprise Desk • {profile?.legal_name || user?.display_name}</h1>
            <p className="welcome-sub">
              Reg No: {profile?.registration_number || 'Under Verification'} • Mandi Base:{' '}
              {profile?.primary_location ? `${profile.primary_location.district}, ${profile.primary_location.state}` : 'Not set'}
            </p>
          </div>
        </div>

        <div className="welcome-actions">
          <button className="btn-primary" onClick={() => onNavigate('create-lot')}>
            + List Aggregated Batch
          </button>
          <button className="btn-secondary" onClick={() => onNavigate('profile')}>
            FPO Profile & Verification
          </button>
        </div>
      </div>

      {/* KPI Stats */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Aggregated Batches</span>
          <span className="kpi-value">{aggregatedLots.length}</span>
          <span className="kpi-sub">Total {lots.length} listings</span>
        </div>

        <div className="kpi-card highlight-card">
          <span className="kpi-label">Pending Buyer Offers</span>
          <span className="kpi-value">{incomingOffers.length}</span>
          <span className="kpi-sub">Direct bulk bids</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Institutional Demands</span>
          <span className="kpi-value">{buyerDemands.length}</span>
          <span className="kpi-sub">Active market requests</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">FPO Trade GMV</span>
          <span className="kpi-value price-text">₹{totalOrdersAmount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
          <span className="kpi-sub">Realized member payouts</span>
        </div>
      </div>

      {/* Aggregated Batches */}
      <div className="card dashboard-table-card">
        <div className="table-card-header">
          <h2>FPO Aggregated Lots & Member Shares ({lots.length})</h2>
          <button className="btn-primary btn-sm" onClick={() => onNavigate('create-lot')}>
            + New Aggregated Listing
          </button>
        </div>

        {loading ? (
          <div className="loading-spinner">Loading FPO batches...</div>
        ) : lots.length === 0 ? (
          <div className="empty-state-sm">
            <p>Your FPO has not listed any aggregated member batches yet.</p>
            <button className="btn-primary btn-sm" onClick={() => onNavigate('create-lot')}>
              + Aggregate Member Harvests
            </button>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Batch Title</th>
                <th>Commodity</th>
                <th>Total Volume</th>
                <th>Type</th>
                <th>Members</th>
                <th>Asking Rate</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {lots.map((lot) => (
                <tr key={lot.id}>
                  <td>
                    <div
                      className="lot-name-link"
                      onClick={() => onNavigate('produce-detail', { lotId: lot.id })}
                    >
                      {lot.title}
                    </div>
                  </td>
                  <td>{lot.commodity_name}</td>
                  <td>{lot.available_quantity} {lot.unit}</td>
                  <td>
                    {lot.is_aggregated ? (
                      <span className="aggregated-badge">Aggregated</span>
                    ) : (
                      <span className="subtext">Single Lot</span>
                    )}
                  </td>
                  <td>{lot.contributions_count > 0 ? `${lot.contributions_count} farmers` : '1'}</td>
                  <td>
                    {lot.asking_price_per_unit ? `₹${lot.asking_price_per_unit.toLocaleString('en-IN')}/${lot.unit}` : 'Negotiable'}
                  </td>
                  <td>
                    <span className={`status-pill status-${lot.status}`}>{lot.status.toUpperCase()}</span>
                  </td>
                  <td>
                    <button
                      className="btn-secondary btn-sm"
                      onClick={() => onNavigate('produce-detail', { lotId: lot.id })}
                    >
                      View ➔
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Match with Institutional Demands */}
      <div className="card dashboard-table-card">
        <div className="table-card-header">
          <h2>Market Buyer Demands to Fulfill ({buyerDemands.length})</h2>
          <button className="btn-link" onClick={() => onNavigate('requirements')}>
            Browse All Demands ➔
          </button>
        </div>

        {buyerDemands.length === 0 ? (
          <div className="empty-state-sm">No active buyer demands found.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Buyer / Organization</th>
                <th>Commodity</th>
                <th>Required Quantity</th>
                <th>Target Rate</th>
                <th>Delivery Destination</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {buyerDemands.slice(0, 5).map((req) => (
                <tr key={req.id}>
                  <td>
                    <strong>{req.buyer_organization || req.buyer_name}</strong>
                  </td>
                  <td>{req.commodity_name}</td>
                  <td>{req.required_quantity} {req.unit}</td>
                  <td className="price-text">
                    {req.target_price_per_unit ? `₹${req.target_price_per_unit.toLocaleString('en-IN')}/${req.unit}` : 'Open'}
                  </td>
                  <td className="subtext">
                    {req.delivery_location ? `${req.delivery_location.district}, ${req.delivery_location.state}` : 'India'}
                  </td>
                  <td>
                    <button
                      className="btn-primary btn-sm"
                      onClick={() => onNavigate('create-lot')}
                    >
                      Create Matching Batch
                    </button>
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
