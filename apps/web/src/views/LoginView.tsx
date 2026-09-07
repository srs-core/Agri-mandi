import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

interface LoginViewProps {
  onNavigate: (view: string, params?: Record<string, unknown>) => void;
}

export const LoginView: React.FC<LoginViewProps> = ({ onNavigate }) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const validate = (): boolean => {
    const errors: { email?: string; password?: string } = {};
    if (!email.trim()) {
      errors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      errors.email = 'Enter a valid email address.';
    }

    if (!password) {
      errors.password = 'Password is required.';
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
      const user = await login(email.trim(), password);
      setSuccessMessage(`Welcome back, ${user.display_name}! Redirecting...`);

      setTimeout(() => {
        if (user.roles.includes('transporter')) {
          onNavigate('transporter-dashboard');
        } else if (user.roles.includes('farmer')) {
          onNavigate('farmer-dashboard');
        } else if (user.roles.includes('buyer')) {
          onNavigate('buyer-dashboard');
        } else if (user.roles.includes('fpo')) {
          onNavigate('fpo-dashboard');
        } else if (user.roles.includes('admin')) {
          onNavigate('admin');
        } else {
          onNavigate('marketplace');
        }
      }, 300);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes('401') || msg.toLowerCase().includes('credential') || msg.toLowerCase().includes('unauthorized') || msg.toLowerCase().includes('invalid')) {
        setError('Email or password is incorrect.');
      } else if (msg.includes('429')) {
        setError('Too many sign in attempts. Please wait a few seconds and try again.');
      } else if (msg.toLowerCase().includes('network') || msg.toLowerCase().includes('failed to fetch')) {
        setError('Unable to connect to AgriMandi. Check your connection and try again.');
      } else {
        setError(msg || 'Sign in failed. Please check your credentials and try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-view-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-logo">🌱</div>
          <div className="auth-brand-tagline">National Agri Trade Exchange</div>
          <h2>Sign in to AgriMandi</h2>
          <p>Access your producer lots, buyer offers, and live logistics orders</p>
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

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <div className="form-group">
            <label htmlFor="email" className="form-label">
              Email Address <span style={{ color: 'var(--color-danger)' }}>*</span>
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              placeholder="e.g. farmer@example.com"
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
            <label htmlFor="password" className="form-label">
              Password <span style={{ color: 'var(--color-danger)' }}>*</span>
            </label>
            <div className="password-input-wrapper">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                placeholder="Enter your password"
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
            {fieldErrors.password && <span className="form-error">{fieldErrors.password}</span>}
          </div>

          <button
            type="submit"
            className="btn-primary btn-block btn-lg"
            disabled={loading}
            style={{ marginTop: '0.75rem' }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div className="auth-footer">
          <span>Don't have an account?</span>
          <button className="btn-link" onClick={() => onNavigate('register')}>
            Register as Farmer, FPO, Buyer or Transporter
          </button>
        </div>
      </div>
    </div>
  );
};
