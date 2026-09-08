import React, { useEffect, useState } from 'react';
import { api, type AdminUser, type PlatformMetrics, type VerificationRequest } from '../api/client';

interface AdminDashboardViewProps {
  onNavigate?: (view: string, params?: Record<string, unknown>) => void;
}

export const AdminDashboardView: React.FC<AdminDashboardViewProps> = () => {
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [verifications, setVerifications] = useState<VerificationRequest[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [tab, setTab] = useState<'verifications' | 'users'>('verifications');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [reviewNotes, setReviewNotes] = useState<string>('');
  const [selectedReq, setSelectedReq] = useState<VerificationRequest | null>(null);
  const [reviewAction, setReviewAction] = useState<'verified' | 'rejected'>('verified');

  const fetchData = React.useCallback(async () => {
    try {
      const [m, v, u] = await Promise.all([
        api.getAdminMetrics(),
        api.getAdminVerifications(),
        api.getAdminUsers(),
      ]);
      setMetrics(m);
      setVerifications(v);
      setUsers(u);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load administration data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const run = async () => {
      if (active) {
        await fetchData();
      }
    };
    void run();
    return () => {
      active = false;
    };
  }, [fetchData]);

  const handleOpenReview = (req: VerificationRequest, action: 'verified' | 'rejected') => {
    setSelectedReq(req);
    setReviewAction(action);
    setReviewNotes(action === 'verified' ? 'Documents and credentials verified.' : 'Missing required documentation.');
  };

  const handleConfirmReview = async () => {
    if (!selectedReq) return;
    setActionLoading(selectedReq.id);
    setError(null);
    setSuccessMsg(null);

    try {
      await api.reviewVerification(selectedReq.id, {
        status: reviewAction,
        reviewer_notes: reviewNotes,
      });
      setSuccessMsg(`Verification request for ${selectedReq.user_name} has been marked as ${reviewAction.toUpperCase()}.`);
      setSelectedReq(null);
      await fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to process verification review.');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="admin-page section-container">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Mandi Administration & Verification Center</h1>
          <p className="page-subtitle">
            Platform-level oversight, stakeholder credential verification, trade volume analytics, and compliance governance.
          </p>
        </div>
      </div>

      {error && <div className="alert-box alert-error">{error}</div>}
      {successMsg && <div className="alert-box alert-success">{successMsg}</div>}

      {/* Platform KPI Grid */}
      {metrics && (
        <div className="admin-kpi-grid">
          <div className="kpi-card">
            <span className="kpi-label">Total Platform Users</span>
            <span className="kpi-value">{metrics.total_users}</span>
            <span className="kpi-sub">
              {metrics.total_farmers} Farmers • {metrics.total_fpos} FPOs • {metrics.total_buyers} Buyers
            </span>
          </div>

          <div className="kpi-card highlight-card">
            <span className="kpi-label">Pending Verifications</span>
            <span className="kpi-value">{metrics.pending_verifications}</span>
            <span className="kpi-sub">Producer / FPO documents</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Active Mandi Lots</span>
            <span className="kpi-value">{metrics.active_produce_lots}</span>
            <span className="kpi-sub">{metrics.total_commodities} active crops</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Trade Offers / Bids</span>
            <span className="kpi-value">{metrics.total_offers}</span>
            <span className="kpi-sub">{metrics.pending_offers} pending</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Confirmed Contracts</span>
            <span className="kpi-value">{metrics.confirmed_orders}</span>
            <span className="kpi-sub">Executed orders</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Platform Gross Merchandise Value</span>
            <span className="kpi-value price-text">₹{metrics.total_gmv.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
            <span className="kpi-sub">Total traded turnover</span>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="tabs-header-row">
        <div className="tab-buttons">
          <button
            className={`tab-btn ${tab === 'verifications' ? 'active' : ''}`}
            onClick={() => setTab('verifications')}
          >
            🛡️ Verification Queue ({verifications.filter((v) => v.status === 'pending').length} Pending)
          </button>
          <button
            className={`tab-btn ${tab === 'users' ? 'active' : ''}`}
            onClick={() => setTab('users')}
          >
            👥 Platform Users Directory ({users.length})
          </button>
        </div>
      </div>

      {/* Verification Queue Tab */}
      {tab === 'verifications' && (
        <div className="card dashboard-table-card">
          <div className="table-card-header">
            <h2>Producer & Business Verification Requests</h2>
            <span className="subtext">Verify 7/12 land records, FPO registration certificates, and GSTINs</span>
          </div>

          {loading ? (
            <div className="loading-spinner">Loading queue...</div>
          ) : verifications.length === 0 ? (
            <div className="empty-state-sm">No verification requests submitted yet.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Requester</th>
                  <th>Role</th>
                  <th>Document Reference</th>
                  <th>Status</th>
                  <th>Submitted Date</th>
                  <th>Reviewer Notes</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {verifications.map((req) => (
                  <tr key={req.id}>
                    <td>
                      <strong>{req.user_name}</strong>
                      <div className="subtext">{req.user_email}</div>
                    </td>
                    <td>
                      <span className={`role-pill role-${req.user_role}`}>
                        {req.user_role.toUpperCase()}
                      </span>
                    </td>
                    <td>
                      <code className="doc-ref-text">{req.document_reference || 'Self-attested registration'}</code>
                    </td>
                    <td>
                      <span className={`status-pill status-${req.status}`}>
                        {req.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="subtext">{new Date(req.created_at).toLocaleDateString()}</td>
                    <td className="subtext">{req.reviewer_notes || '—'}</td>
                    <td>
                      {req.status === 'pending' ? (
                        <div className="action-btn-group">
                          <button
                            className="btn-success-sm"
                            onClick={() => handleOpenReview(req, 'verified')}
                          >
                            ✓ Verify
                          </button>
                          <button
                            className="btn-danger-sm"
                            onClick={() => handleOpenReview(req, 'rejected')}
                          >
                            ✕ Reject
                          </button>
                        </div>
                      ) : (
                        <span className="subtext">Reviewed</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Users Directory Tab */}
      {tab === 'users' && (
        <div className="card dashboard-table-card">
          <div className="table-card-header">
            <h2>Registered Platform Users ({users.length})</h2>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>User / Organization</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Roles</th>
                <th>Account Status</th>
                <th>Verification</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <strong>{u.display_name}</strong>
                  </td>
                  <td>{u.email}</td>
                  <td>{u.phone_number || '—'}</td>
                  <td>
                    {u.roles.map((r) => (
                      <span key={r} className={`role-pill role-${r}`}>
                        {r.toUpperCase()}
                      </span>
                    ))}
                  </td>
                  <td>
                    <span className={`status-pill status-${u.status}`}>{u.status.toUpperCase()}</span>
                  </td>
                  <td>
                    <span className={`status-pill status-${u.verification_status}`}>
                      {u.verification_status.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Review Modal */}
      {selectedReq && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h2>
                {reviewAction === 'verified' ? 'Approve Verification' : 'Reject Verification'}
              </h2>
              <button className="btn-close" onClick={() => setSelectedReq(null)}>✕</button>
            </div>

            <div className="modal-body">
              <p>
                <strong>Applicant:</strong> {selectedReq.user_name} ({selectedReq.user_role.toUpperCase()})
              </p>
              <p>
                <strong>Document Reference:</strong> {selectedReq.document_reference || 'N/A'}
              </p>

              <div className="form-group">
                <label htmlFor="reviewNotes">Auditor / Mandi Officer Notes</label>
                <textarea
                  id="reviewNotes"
                  rows={3}
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  className="form-textarea"
                />
              </div>

              <div className="modal-actions-row">
                <button className="btn-secondary" onClick={() => setSelectedReq(null)}>
                  Cancel
                </button>
                <button
                  className={reviewAction === 'verified' ? 'btn-primary' : 'btn-danger'}
                  onClick={handleConfirmReview}
                  disabled={actionLoading === selectedReq.id}
                >
                  {actionLoading === selectedReq.id ? 'Processing...' : `Confirm ${reviewAction.toUpperCase()}`}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
