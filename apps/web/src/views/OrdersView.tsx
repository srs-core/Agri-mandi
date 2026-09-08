import React, { useEffect, useState } from 'react';
import { api, type Order } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface OrdersViewProps {
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const OrdersView: React.FC<OrdersViewProps> = ({ onNavigate }) => {
  const { user } = useAuth();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchOrders = React.useCallback(async () => {
    try {
      const data = await api.getOrders();
      setOrders(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load orders.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const run = async () => {
      if (active) {
        await fetchOrders();
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [fetchOrders]);

  const handleStatusUpdate = async (orderId: string, newStatus: 'confirmed' | 'fulfilment' | 'delivered' | 'cancelled') => {
    setActionLoading(orderId);
    setError(null);
    setSuccessMsg(null);
    try {
      await api.updateOrderStatus(orderId, newStatus);
      setSuccessMsg(`Order status updated to ${newStatus.toUpperCase()}.`);
      await fetchOrders();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update order status.');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="orders-page section-container">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Trade Orders & Fulfilment</h1>
          <p className="page-subtitle">
            Track confirmed commercial commodity trades, farm-gate dispatch, and final delivery milestones.
          </p>
        </div>
      </div>

      {error && <div className="alert-box alert-error">{error}</div>}
      {successMsg && <div className="alert-box alert-success">{successMsg}</div>}

      {loading ? (
        <div className="loading-spinner">Loading commercial orders...</div>
      ) : orders.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📦</div>
          <h3>No Orders Yet</h3>
          <p>Once a seller accepts a commercial offer, the binding contract order appears here.</p>
          <button className="btn-primary" onClick={() => onNavigate('marketplace')}>
            Explore Marketplace Lots
          </button>
        </div>
      ) : (
        <div className="orders-list-grid">
          {orders.map((order) => {
            const isSeller = user?.id === order.seller_user_id;
            const isBuyer = user?.id === order.buyer_user_id;

            return (
              <div key={order.id} className="card order-card">
                <div className="order-header-row">
                  <div>
                    <span className="order-id-tag">ORDER #{order.id.slice(0, 8)}</span>
                    <span className="subtext">
                      Confirmed: {order.confirmed_at ? new Date(order.confirmed_at).toLocaleDateString() : 'N/A'}
                    </span>
                  </div>
                  <span className={`status-pill status-${order.status}`}>{order.status.toUpperCase()}</span>
                </div>

                <div className="order-parties-row">
                  <div className="party-box">
                    <span className="party-role">Seller (Producer)</span>
                    <strong className="party-name">{order.seller_name}</strong>
                    {isSeller && <span className="you-pill">You</span>}
                  </div>
                  <div className="party-arrow">➔</div>
                  <div className="party-box">
                    <span className="party-role">Buyer (Procurement)</span>
                    <strong className="party-name">{order.buyer_name}</strong>
                    {isBuyer && <span className="you-pill">You</span>}
                  </div>
                </div>

                {/* Items */}
                <div className="order-items-box">
                  <h4>Order Commodity Items ({order.items.length})</h4>
                  {order.items.map((item) => (
                    <div key={item.id} className="order-item-row">
                      <div>
                        <strong>{item.commodity_name}</strong>
                        <span className="subtext">
                          {' '}• {item.quantity} {item.unit} @ ₹{item.agreed_price_per_unit.toLocaleString('en-IN')}/{item.unit}
                        </span>
                      </div>
                      <div className="item-subtotal font-bold">
                        ₹{item.total_item_amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                      </div>
                    </div>
                  ))}
                </div>

                {/* Total & Delivery */}
                <div className="order-summary-row">
                  <div>
                    {order.delivery_location && (
                      <span className="subtext">
                        📍 Yard: {order.delivery_location.name} ({order.delivery_location.district}, {order.delivery_location.state})
                      </span>
                    )}
                  </div>
                  <div className="order-total-metric">
                    <span className="metric-label">Total Commercial GMV:</span>
                    <span className="total-deal-amount font-bold">
                      ₹{order.total_amount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>

                {/* Order Lifecycle Actions */}
                <div className="order-actions-row">
                  {order.status === 'confirmed' && (
                    <button
                      className="btn-primary btn-sm"
                      onClick={() => handleStatusUpdate(order.id, 'fulfilment')}
                      disabled={actionLoading === order.id}
                    >
                      {actionLoading === order.id ? 'Updating...' : '🚚 Advance to In-Transit / Fulfilment'}
                    </button>
                  )}

                  {order.status === 'fulfilment' && (
                    <button
                      className="btn-success-sm"
                      onClick={() => handleStatusUpdate(order.id, 'delivered')}
                      disabled={actionLoading === order.id}
                    >
                      {actionLoading === order.id ? 'Updating...' : '✓ Mark Completed / Delivered'}
                    </button>
                  )}

                  {(order.status === 'confirmed' || order.status === 'fulfilment') && (
                    <button
                      className="btn-danger-sm"
                      onClick={() => handleStatusUpdate(order.id, 'cancelled')}
                      disabled={actionLoading === order.id}
                    >
                      Cancel Order
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
