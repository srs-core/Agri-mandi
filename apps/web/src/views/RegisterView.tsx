import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

interface RegisterViewProps {
  initialRole?: 'farmer' | 'fpo' | 'buyer' | 'transporter';
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

const FarmerIcon: React.FC = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 22v-9" />
    <path d="M12 13a5 5 0 0 0-5-5c0 5 5 5 5 5Z" />
    <path d="M12 13a5 5 0 0 1 5-5c0 5-5 5-5 5Z" />
    <path d="M4 22h16" />
  </svg>
);

const FPOIcon: React.FC = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 21h18" />
    <path d="M5 21V7l8-4v18" />
    <path d="M13 10h6v11" />
    <path d="M9 9v.01" />
    <path d="M9 13v.01" />
    <path d="M9 17v.01" />
  </svg>
);

const BuyerIcon: React.FC = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" />
    <path d="M3 6h18" />
    <path d="M16 10a4 4 0 0 1-8 0" />
  </svg>
);

const TransporterIcon: React.FC = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M10 17h4V5H2v12h3" />
    <path d="M20 17h2v-6l-3-4h-5v10h2" />
    <circle cx="7.5" cy="17.5" r="2.5" />
    <circle cx="17.5" cy="17.5" r="2.5" />
  </svg>
);

export const RegisterView: React.FC<RegisterViewProps> = ({ initialRole, onNavigate }) => {
  const { register } = useAuth();
  const [role, setRole] = useState<'farmer' | 'fpo' | 'buyer' | 'transporter'>(initialRole || 'farmer');
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{
    displayName?: string;
    email?: string;
    phoneNumber?: string;
    password?: string;
    confirmPassword?: string;
  }>({});

  const [prevInitialRole, setPrevInitialRole] = useState(initialRole);
  if (initialRole !== prevInitialRole) {
    setPrevInitialRole(initialRole);
    if (initialRole) {
      setRole(initialRole);
    }
  }

  const validate = (): boolean => {
    const errors: typeof fieldErrors = {};

    if (!displayName.trim()) {
      errors.displayName = 'Name or business name is required.';
    } else if (displayName.trim().length < 2) {
      errors.displayName = 'Name must be at least 2 characters.';
    }

    if (!email.trim()) {
      errors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errors.email = 'Enter a valid email address.';
    }

    if (phoneNumber.trim() && !/^\+?[0-9\s-]{8,20}$/.test(phoneNumber.trim())) {
      errors.phoneNumber = 'Enter a valid phone number (8-15 digits).';
    }

    if (!password) {
      errors.password = 'Password is required.';
    } else if (password.length < 8) {
      errors.password = 'Password must contain at least 8 characters.';
    }

    if (!confirmPassword) {
      errors.confirmPassword = 'Confirm your password.';
    } else if (password !== confirmPassword) {
      errors.confirmPassword = 'Passwords do not match.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (!validate()) {
      return;
    }

    setLoading(true);
    try {
      const user = await register({
        email: email.trim(),
        password,
        display_name: displayName.trim(),
        role,
        phone_number: phoneNumber.trim() || undefined,
      });

      setSuccessMessage('Account created successfully! Preparing your workspace...');

      setTimeout(() => {
        if (user.roles.includes('transporter') || role === 'transporter') {
          onNavigate('transporter-dashboard');
        } else if (user.roles.includes('farmer') || role === 'farmer') {
          onNavigate('farmer-dashboard');
        } else if (user.roles.includes('buyer') || role === 'buyer') {
          onNavigate('buyer-dashboard');
        } else if (user.roles.includes('fpo') || role === 'fpo') {
          onNavigate('fpo-dashboard');
        } else {
          onNavigate('marketplace');
        }
      }, 350);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('409') || msg.toLowerCase().includes('already exists') || msg.toLowerCase().includes('duplicate')) {
        setError('An account with this email already exists.');
        setFieldErrors((prev) => ({ ...prev, email: 'Email already registered.' }));
      } else if (msg.includes('422') || msg.toLowerCase().includes('validation')) {
        setError('Please correct the highlighted fields and try again.');
      } else if (msg.toLowerCase().includes('network') || msg.toLowerCase().includes('failed to fetch')) {
        setError('Unable to connect to AgriMandi. Check your connection and try again.');
      } else {
        setError(msg || 'Registration failed. Please check your details and try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const getRoleDisplayNameLabel = () => {
    switch (role) {
      case 'farmer':
        return 'Full Name (Farmer)';
      case 'fpo':
        return 'Organization Name (FPO / Cooperative)';
      case 'buyer':
        return 'Business / Enterprise Name';
      case 'transporter':
        return 'Fleet / Transport Business Name';
      default:
        return 'Full Name';
    }
  };

  const getRoleDisplayNamePlaceholder = () => {
    switch (role) {
      case 'farmer':
        return 'e.g. Ramesh Patil';
      case 'fpo':
        return 'e.g. Sahyadri Farmers Producer Co Ltd';
      case 'buyer':
        return 'e.g. MahaAgri Agro Processing Pvt Ltd';
      case 'transporter':
        return 'e.g. Kisan Express Logistics';
      default:
        return 'Enter your name';
    }
  };

  return (
    <div className="auth-view-container">
      <div className="auth-card register-card">
        <div className="auth-header">
          <div className="auth-logo">🌱</div>
          <div className="auth-brand-tagline">National Agri Trade Exchange</div>
          <h2>Create Your Account</h2>
          <p>Join verified agricultural producers, buyers, FPOs, and logistics carriers</p>
        </div>

        {error && (
          <div className="alert-box alert-error" style={{ marginBottom: '1.25rem' }}>
            <span>✕</span>
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div className="alert-box alert-success" style={{ marginBottom: '1.25rem' }}>
            <span>✓</span>
            <span>{successMessage}</span>
          </div>
        )}

        {/* Role Selector Tabs (4 Cards) */}
        <div style={{ marginBottom: '1.25rem' }}>
          <label className="form-label" style={{ marginBottom: '0.5rem' }}>
            Select Trading Role <span style={{ color: 'var(--color-danger)' }}>*</span>
          </label>
          <div className="role-selector-grid">
            <button
              type="button"
              className={`role-option-btn ${role === 'farmer' ? 'selected' : ''}`}
              onClick={() => setRole('farmer')}
            >
              <span className="role-icon"><FarmerIcon /></span>
              <span className="role-label">Farmer</span>
              <span className="role-desc">Sell Produce</span>
            </button>

            <button
              type="button"
              className={`role-option-btn ${role === 'fpo' ? 'selected' : ''}`}
              onClick={() => setRole('fpo')}
            >
              <span className="role-icon"><FPOIcon /></span>
              <span className="role-label">FPO</span>
              <span className="role-desc">Aggregate Crops</span>
            </button>

            <button
              type="button"
              className={`role-option-btn ${role === 'buyer' ? 'selected' : ''}`}
              onClick={() => setRole('buyer')}
            >
              <span className="role-icon"><BuyerIcon /></span>
              <span className="role-label">Buyer</span>
              <span className="role-desc">Source Produce</span>
            </button>

            <button
              type="button"
              className={`role-option-btn ${role === 'transporter' ? 'selected' : ''}`}
              onClick={() => setRole('transporter')}
            >
              <span className="role-icon"><TransporterIcon /></span>
              <span className="role-label">Transporter</span>
              <span className="role-desc">Move Freight</span>
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          {/* Display Name */}
          <div className="form-group">
            <label htmlFor="displayName" className="form-label">
              {getRoleDisplayNameLabel()} <span style={{ color: 'var(--color-danger)' }}>*</span>
            </label>
            <input
              id="displayName"
              type="text"
              required
              placeholder={getRoleDisplayNamePlaceholder()}
              value={displayName}
              onChange={(e) => {
                setDisplayName(e.target.value);
                if (fieldErrors.displayName) setFieldErrors((prev) => ({ ...prev, displayName: undefined }));
              }}
              className="form-input"
              style={fieldErrors.displayName ? { borderColor: 'var(--color-danger)' } : undefined}
            />
            {fieldErrors.displayName && <span className="form-error">{fieldErrors.displayName}</span>}
          </div>

          {/* Email and Phone Grid */}
          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="email" className="form-label">
                Email Address <span style={{ color: 'var(--color-danger)' }}>*</span>
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                placeholder="name@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (fieldErrors.email) setFieldErrors((prev) => ({ ...prev, email: undefined }));
                }}
                className="form-input"
                style={fieldErrors.email ? { borderColor: 'var(--color-danger)' } : undefined}
              />
              {fieldErrors.email && <span className="form-error">{fieldErrors.email}</span>}
            </div>

            <div className="form-group">
              <label htmlFor="phoneNumber" className="form-label">
                Mobile Number <span className="form-helper">(Optional)</span>
              </label>
              <input
                id="phoneNumber"
                type="tel"
                placeholder="+91 9876543210"
                value={phoneNumber}
                onChange={(e) => {
                  setPhoneNumber(e.target.value);
                  if (fieldErrors.phoneNumber) setFieldErrors((prev) => ({ ...prev, phoneNumber: undefined }));
                }}
                className="form-input"
                style={fieldErrors.phoneNumber ? { borderColor: 'var(--color-danger)' } : undefined}
              />
              {fieldErrors.phoneNumber && <span className="form-error">{fieldErrors.phoneNumber}</span>}
            </div>
          </div>

          {/* Password and Confirm Password Grid */}
          <div className="form-grid-2">
            <div className="form-group">
              <label htmlFor="password" className="form-label">
                Password <span style={{ color: 'var(--color-danger)' }}>*</span>
              </label>
              <div className="password-input-wrapper">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  minLength={8}
                  placeholder="Min. 8 characters"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (fieldErrors.password) setFieldErrors((prev) => ({ ...prev, password: undefined }));
                  }}
                  className="form-input"
                  style={fieldErrors.password ? { borderColor: 'var(--color-danger)' } : undefined}
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              {fieldErrors.password ? (
                <span className="form-error">{fieldErrors.password}</span>
              ) : password.length > 0 && password.length < 8 ? (
                <span className="password-hint invalid">✕ Must be at least 8 characters</span>
              ) : password.length >= 8 ? (
                <span className="password-hint valid">✓ Password length requirement met</span>
              ) : (
                <span className="form-helper">At least 8 characters</span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="confirmPassword" className="form-label">
                Confirm Password <span style={{ color: 'var(--color-danger)' }}>*</span>
              </label>
              <div className="password-input-wrapper">
                <input
                  id="confirmPassword"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  placeholder="Re-enter password"
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (fieldErrors.confirmPassword) setFieldErrors((prev) => ({ ...prev, confirmPassword: undefined }));
                  }}
                  className="form-input"
                  style={fieldErrors.confirmPassword ? { borderColor: 'var(--color-danger)' } : undefined}
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                >
                  {showConfirmPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              {fieldErrors.confirmPassword ? (
                <span className="form-error">{fieldErrors.confirmPassword}</span>
              ) : confirmPassword.length > 0 && confirmPassword !== password ? (
                <span className="password-hint invalid">✕ Passwords do not match</span>
              ) : confirmPassword.length > 0 && confirmPassword === password ? (
                <span className="password-hint valid">✓ Passwords match</span>
              ) : (
                <span className="form-helper">Must match password above</span>
              )}
            </div>
          </div>

          <button
            type="submit"
            className="btn-primary btn-block btn-lg"
            disabled={loading}
            style={{ marginTop: '0.75rem' }}
          >
            {loading ? 'Creating Account...' : `Register as ${role.toUpperCase()}`}
          </button>
        </form>

        <div className="auth-footer">
          <span>Already registered?</span>
          <button className="btn-link" onClick={() => onNavigate('login')}>
            Sign in to your account
          </button>
        </div>
      </div>
    </div>
  );
};
