import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api, type Notification } from '../api/client';

interface NavbarProps {
  currentView: string;
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ currentView, onNavigate }) => {
  const { user, profile, isAuthenticated, logout } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [showNotifications, setShowNotifications] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    const fetchNotifications = async () => {
      try {
        const list = await api.getNotifications();
        setNotifications(list);
      } catch {
        // ignore
      }
    };

    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  const deduplicatedNotifications = Array.from(
    new Map(notifications.map((n) => [n.id, n])).values()
  );

  const unreadCount = deduplicatedNotifications.filter((n) => !n.read_at).length;

  const handleMarkRead = async (id: string) => {
    try {
      await api.markNotificationRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n))
      );
    } catch {
      // ignore
    }
  };

  const handleNotificationClick = async (n: Notification) => {
    // 1. Mark as read
    if (!n.read_at) {
      void handleMarkRead(n.id);
    }
    // 2. Close tray
    setShowNotifications(false);

    // 3. Navigate to appropriate destination
    const data = n.data_json || {};
    if (n.notification_type === 'TRANSPORT_OPPORTUNITY_CREATED' || data.opportunity_id) {
      onNavigate('transporter-dashboard', { opportunityId: data.opportunity_id });
      return;
    }

    if (n.notification_type === 'TRANSPORT_ASSIGNED' || (data.shipment_id && isTransporter)) {
      onNavigate('transporter-dashboard', { shipmentId: data.shipment_id });
      return;
    }

    if (n.notification_type === 'CARRIER_ASSIGNED' || data.order_id) {
      onNavigate('orders');
      return;
    }

    if (data.lot_id) {
      onNavigate('produce-detail', { lotId: data.lot_id });
      return;
    }

    if (data.offer_id) {
      onNavigate('offers', { offerId: data.offer_id });
      return;
    }
  };

  const primaryRole = user?.roles[0] || '';
  const isFarmer = user?.roles.includes('farmer');
  const isFPO = user?.roles.includes('fpo');
  const isBuyer = user?.roles.includes('buyer');
  const isTransporter = user?.roles.includes('transporter');
  const isAdmin = user?.roles.includes('admin');

  return (
    <header className="navbar-container">
      <div className="navbar-content">
        <div className="brand-section" onClick={() => onNavigate('landing')} role="button" tabIndex={0}>
          <div className="brand-logo">🌱</div>
          <div>
            <div className="brand-name">AgriMandi</div>
            <div className="brand-tagline">National Agri Trade Exchange</div>
          </div>
        </div>

        <nav className="nav-links">
          <button
            className={`nav-link ${currentView === 'marketplace' ? 'active' : ''}`}
            onClick={() => onNavigate('marketplace')}
          >
            Marketplace
          </button>

          <button
            className={`nav-link ${currentView === 'requirements' ? 'active' : ''}`}
            onClick={() => onNavigate('requirements')}
          >
            Buyer Demands
          </button>

          {isAuthenticated && (
            <>
              {isFarmer && (
                <button
                  className={`nav-link ${currentView === 'farmer-dashboard' ? 'active' : ''}`}
                  onClick={() => onNavigate('farmer-dashboard')}
                >
                  Farmer Hub
                </button>
              )}

              {isFPO && (
                <button
                  className={`nav-link ${currentView === 'fpo-dashboard' ? 'active' : ''}`}
                  onClick={() => onNavigate('fpo-dashboard')}
                >
                  FPO Hub
                </button>
              )}

              {isBuyer && (
                <button
                  className={`nav-link ${currentView === 'buyer-dashboard' ? 'active' : ''}`}
                  onClick={() => onNavigate('buyer-dashboard')}
                >
                  Buyer Desk
                </button>
              )}

              {isTransporter && (
                <button
                  className={`nav-link ${currentView === 'transporter-dashboard' || currentView === 'transporter-opportunities' || currentView === 'transporter-vehicles' || currentView === 'transporter-opportunity' ? 'active' : ''}`}
                  onClick={() => onNavigate('transporter-dashboard')}
                >
                  🚚 Transporter Hub
                </button>
              )}

              {isAdmin && (
                <button
                  className={`nav-link ${currentView === 'admin' ? 'active' : ''}`}
                  onClick={() => onNavigate('admin')}
                >
                  Admin Portal
                </button>
              )}

              <button
                className={`nav-link ${currentView === 'offers' ? 'active' : ''}`}
                onClick={() => onNavigate('offers')}
              >
                Offers
              </button>

              <button
                className={`nav-link ${currentView === 'orders' ? 'active' : ''}`}
                onClick={() => onNavigate('orders')}
              >
                Orders
              </button>
            </>
          )}

          <button
            className={`nav-link ${currentView === 'logistics-route' ? 'active' : ''}`}
            onClick={() => onNavigate('logistics-route')}
          >
            Route Map
          </button>
        </nav>

        <div className="navbar-actions">
          {isAuthenticated ? (
            <div className="user-menu">
              <div className="notification-bell-wrapper">
                <button
                  className="icon-button notification-btn"
                  onClick={() => setShowNotifications(!showNotifications)}
                  title="Notifications"
                >
                  🔔
                  {unreadCount > 0 && <span className="notification-badge">{unreadCount}</span>}
                </button>

                {showNotifications && (
                  <div className="notifications-dropdown">
                    <div className="notifications-header">
                      <span>Notifications</span>
                      <button
                        className="btn-text-sm"
                        onClick={() => setShowNotifications(false)}
                      >
                        ✕
                      </button>
                    </div>
                    <div className="notifications-list">
                      {deduplicatedNotifications.length === 0 ? (
                        <div className="notifications-empty">No notifications yet</div>
                      ) : (
                        deduplicatedNotifications.slice(0, 10).map((n) => (
                          <div
                            key={n.id}
                            className={`notification-item ${!n.read_at ? 'unread' : ''}`}
                            onClick={() => void handleNotificationClick(n)}
                            role="button"
                            tabIndex={0}
                            style={{ cursor: 'pointer' }}
                          >
                            <div className="notif-title">{n.title}</div>
                            <div className="notif-body">{n.body}</div>
                            <div className="notif-time">
                              {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div
                className="user-profile-badge"
                onClick={() => onNavigate('profile')}
                role="button"
                tabIndex={0}
              >
                <div className="user-name">{user?.display_name}</div>
                <div className="user-subtext">
                  <span className={`role-pill role-${primaryRole}`}>{primaryRole.toUpperCase()}</span>
                  {profile?.verification_status === 'verified' && (
                    <span className="badge-verified" title="Verified Producer/Entity">✓ Verified</span>
                  )}
                </div>
              </div>

              <button className="btn-secondary btn-sm" onClick={logout}>
                Logout
              </button>
            </div>
          ) : (
            <div className="auth-buttons">
              <button className="btn-secondary" onClick={() => onNavigate('login')}>
                Sign In
              </button>
              <button className="btn-primary" onClick={() => onNavigate('register')}>
                Register
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
