import React, { useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';

interface ProfileViewProps {
  onNavigate?: (view: string, params?: Record<string, unknown>) => void;
}

export const ProfileView: React.FC<ProfileViewProps> = () => {
  const { user, profile, refreshProfile } = useAuth();

  const [displayName, setDisplayName] = useState(profile?.display_name || '');
  const [phoneNumber, setPhoneNumber] = useState(profile?.phone_number || '');
  const [farmName, setFarmName] = useState(profile?.farm_name || '');
  const [landArea, setLandArea] = useState(profile?.land_area_hectares ? String(profile.land_area_hectares) : '');
  const [legalName, setLegalName] = useState(profile?.legal_name || '');
  const [regNo, setRegNo] = useState(profile?.registration_number || '');
  const [orgName, setOrgName] = useState(profile?.organization_name || '');
  const [gstin, setGstin] = useState(profile?.gstin || '');

  // Primary Location
  const [locName, setLocName] = useState(profile?.primary_location?.name || '');
  const [village, setVillage] = useState(profile?.primary_location?.village || '');
  const [taluka, setTaluka] = useState(profile?.primary_location?.taluka || '');
  const [district, setDistrict] = useState(profile?.primary_location?.district || '');
  const [state, setState] = useState(profile?.primary_location?.state || 'Maharashtra');
  const [postalCode, setPostalCode] = useState(profile?.primary_location?.postal_code || '');

  // Verification request
  const [docRef, setDocRef] = useState('');
  const [submittingVer, setSubmittingVer] = useState(false);
  const [verSuccess, setVerSuccess] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setSaving(true);

    try {
      await api.updateProfile({
        display_name: displayName,
        phone_number: phoneNumber || undefined,
        farm_name: farmName || undefined,
        land_area_hectares: landArea ? Number(landArea) : undefined,
        legal_name: legalName || undefined,
        registration_number: regNo || undefined,
        organization_name: orgName || undefined,
        gstin: gstin || undefined,
        primary_location: locName
          ? {
              name: locName,
              village: village || undefined,
              taluka: taluka || undefined,
              district: district || undefined,
              state,
              postal_code: postalCode || undefined,
            }
          : undefined,
      });
      setSuccessMsg('Profile and primary location updated successfully!');
      await refreshProfile();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update profile.');
    } finally {
      setSaving(false);
    }
  };

  const handleRequestVerification = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingVer(true);
    setVerSuccess(null);
    setError(null);

    try {
      await api.submitVerificationRequest({
        document_reference: docRef,
      });
      setVerSuccess('Verification request submitted! Mandi officers will review your documents.');
      setDocRef('');
      await refreshProfile();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit verification request.');
    } finally {
      setSubmittingVer(false);
    }
  };

  const isFarmer = user?.roles.includes('farmer');
  const isFPO = user?.roles.includes('fpo');
  const isBuyer = user?.roles.includes('buyer');

  return (
    <div className="profile-page section-container">
      <div className="page-header-row">
        <div>
          <h1 className="page-title">Profile & Location Settings</h1>
          <p className="page-subtitle">
            Manage your account identity, agricultural land records, and verified trade credentials.
          </p>
        </div>
      </div>

      {error && <div className="alert-box alert-error">{error}</div>}
      {successMsg && <div className="alert-box alert-success">{successMsg}</div>}
      {verSuccess && <div className="alert-box alert-success">{verSuccess}</div>}

      <div className="profile-layout-grid">
        {/* Main Edit Form */}
        <div className="profile-form-col">
          <form onSubmit={handleSaveProfile} className="form-card">
            <div className="form-section">
              <h2 className="form-section-title">1. Basic Identity</h2>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="displayName">Display / Trading Name *</label>
                  <input
                    id="displayName"
                    type="text"
                    required
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="email">Email Address</label>
                  <input id="email" type="email" disabled value={user?.email || ''} className="form-input disabled" />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="phoneNumber">Phone / Contact Number</label>
                  <input
                    id="phoneNumber"
                    type="tel"
                    placeholder="+91 9876543210"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Assigned Role(s)</label>
                  <div className="roles-pill-row">
                    {user?.roles.map((r) => (
                      <span key={r} className={`role-pill role-${r}`}>
                        {r.toUpperCase()}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Role-Specific Fields */}
            {isFarmer && (
              <div className="form-section">
                <h2 className="form-section-title">2. Farm Specifics</h2>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="farmName">Farm / Estate Name</label>
                    <input
                      id="farmName"
                      type="text"
                      placeholder="e.g. Patil Organic Farms"
                      value={farmName}
                      onChange={(e) => setFarmName(e.target.value)}
                      className="form-input"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="landArea">Total Land Area (Hectares)</label>
                    <input
                      id="landArea"
                      type="number"
                      step="any"
                      placeholder="e.g. 8.5"
                      value={landArea}
                      onChange={(e) => setLandArea(e.target.value)}
                      className="form-input"
                    />
                  </div>
                </div>
              </div>
            )}

            {isFPO && (
              <div className="form-section">
                <h2 className="form-section-title">2. FPO Legal Entity Information</h2>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="legalName">FPO Registered Legal Name</label>
                    <input
                      id="legalName"
                      type="text"
                      placeholder="e.g. Nashik Farmers Producer Co. Ltd"
                      value={legalName}
                      onChange={(e) => setLegalName(e.target.value)}
                      className="form-input"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="regNo">ROC / Cooperative Registration Number</label>
                    <input
                      id="regNo"
                      type="text"
                      placeholder="e.g. U01111MH2021PTC123456"
                      value={regNo}
                      onChange={(e) => setRegNo(e.target.value)}
                      className="form-input"
                    />
                  </div>
                </div>
              </div>
            )}

            {isBuyer && (
              <div className="form-section">
                <h2 className="form-section-title">2. Commercial Buyer & Business Entity</h2>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="orgName">Company / Firm Legal Name</label>
                    <input
                      id="orgName"
                      type="text"
                      placeholder="e.g. Agro Processing Mills Ltd"
                      value={orgName}
                      onChange={(e) => setOrgName(e.target.value)}
                      className="form-input"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="gstin">GSTIN / Tax ID</label>
                    <input
                      id="gstin"
                      type="text"
                      placeholder="e.g. 27AAAAA0000A1Z5"
                      value={gstin}
                      onChange={(e) => setGstin(e.target.value)}
                      className="form-input"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Primary Location */}
            <div className="form-section">
              <h2 className="form-section-title">3. Primary Location / Farm Gate Base</h2>

              <div className="form-group">
                <label htmlFor="locName">Location Name</label>
                <input
                  id="locName"
                  type="text"
                  placeholder="e.g. Niphad Farm Headquarters"
                  value={locName}
                  onChange={(e) => setLocName(e.target.value)}
                  className="form-input"
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="village">Village / Town</label>
                  <input
                    id="village"
                    type="text"
                    value={village}
                    onChange={(e) => setVillage(e.target.value)}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="taluka">Taluka / Tehsil</label>
                  <input
                    id="taluka"
                    type="text"
                    value={taluka}
                    onChange={(e) => setTaluka(e.target.value)}
                    className="form-input"
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="district">District</label>
                  <input
                    id="district"
                    type="text"
                    value={district}
                    onChange={(e) => setDistrict(e.target.value)}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="state">State</label>
                  <input
                    id="state"
                    type="text"
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="postalCode">PIN Code</label>
                  <input
                    id="postalCode"
                    type="text"
                    value={postalCode}
                    onChange={(e) => setPostalCode(e.target.value)}
                    className="form-input"
                  />
                </div>
              </div>
            </div>

            <div className="form-actions-bar">
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? 'Saving Profile...' : 'Save Profile & Locations'}
              </button>
            </div>
          </form>
        </div>

        {/* Verification Status & Request Sidebar */}
        <div className="profile-sidebar-col">
          <div className="card verification-card">
            <h3>Mandi Verification Status</h3>

            <div className="verification-status-banner">
              <span className={`status-badge-large status-${profile?.verification_status}`}>
                {profile?.verification_status === 'verified'
                  ? '✓ VERIFIED PRODUCER'
                  : profile?.verification_status === 'rejected'
                  ? '✕ VERIFICATION REJECTED'
                  : '⏳ VERIFICATION PENDING'}
              </span>
            </div>

            <p className="subtext">
              Verified accounts receive the official green verification checkmark on all produce listings,
              higher buyer visibility, and priority trading status on the national exchange.
            </p>

            {profile?.verification_status !== 'verified' && (
              <form onSubmit={handleRequestVerification} className="ver-request-form">
                <h4>Submit Verification Documents</h4>
                <div className="form-group">
                  <label htmlFor="docRef">Document Reference / ID</label>
                  <textarea
                    id="docRef"
                    rows={3}
                    required
                    placeholder="Enter your 7/12 Land Record number, APMC Trader License #, or FPO Incorporation certificate ID..."
                    value={docRef}
                    onChange={(e) => setDocRef(e.target.value)}
                    className="form-textarea"
                  />
                </div>
                <button type="submit" className="btn-secondary btn-block" disabled={submittingVer}>
                  {submittingVer ? 'Submitting...' : 'Request Mandi Verification'}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
