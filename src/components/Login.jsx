import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { Loader2, Eye, EyeOff } from 'lucide-react';

const Login = () => {
  const { signIn, authError, clearError, isLoading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localError, setLocalError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLocalError('');
    clearError();

    if (!email.trim()) {
      setLocalError('Email is required');
      return;
    }

    if (!password) {
      setLocalError('Password is required');
      return;
    }

    setIsSubmitting(true);
    try {
      const { success, error } = await signIn(email, password);
      
      if (!success && error) {
        setLocalError(error);
      }
    } catch (err) {
      console.error('[Login] Error:', err);
      setLocalError('An unexpected error occurred. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSubmit(e);
    }
  };

  const displayError = localError || authError;

  if (isLoading) {
    return (
      <div className="login-container">
        <div className="login-loading">
          <Loader2 size={40} className="spin" />
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1 className="login-title">ArtSensei Admin</h1>
          <p className="login-subtitle">Sign in to access the testing dashboard</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {displayError && (
            <div className="login-error">
              {displayError}
            </div>
          )}

          <div className="form-group">
            <label htmlFor="email" className="form-label">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="admin@artsensei.com"
              className="form-input"
              disabled={isSubmitting}
              autoComplete="email"
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="password" className="form-label">Password</label>
            <div className="password-input-wrapper">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={handleKeyPress}
                placeholder="Enter your password"
                className="form-input"
                disabled={isSubmitting}
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="password-toggle"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="login-button"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 size={18} className="spin" />
                <span>Signing in...</span>
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div className="login-footer">
          <p>Admin access only</p>
        </div>
      </div>

      <style>{`
        .login-container {
          width: 100dvw;
          height: 100dvh;
          display: flex;
          align-items: center;
          justify-content: center;
          background-color: #f1f5f9;
          background-image: radial-gradient(#e2e8f0 1px, transparent 1px);
          background-size: 20px 20px;
          padding: 20px;
          box-sizing: border-box;
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        .login-loading {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
          color: #64748b;
        }

        .login-loading .spin {
          animation: spin 1s linear infinite;
        }

        .login-card {
          background: #ffffff;
          border-radius: 16px;
          box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
          border: 1px solid #e2e8f0;
          padding: 40px;
          width: 100%;
          max-width: 420px;
        }

        .login-header {
          text-align: center;
          margin-bottom: 32px;
        }

        .login-title {
          font-size: 24px;
          font-weight: 600;
          color: #1e293b;
          margin: 0 0 8px 0;
        }

        .login-subtitle {
          font-size: 14px;
          color: #64748b;
          margin: 0;
        }

        .login-form {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .login-error {
          color: #dc2626;
          font-size: 14px;
          font-weight: 500;
          text-align: center;
        }

        .login-form .form-group {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .login-form .form-label {
          font-size: 14px;
          font-weight: 500;
          color: #1e293b;
        }

        .login-form .form-input {
          padding: 12px 16px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          font-size: 15px;
          transition: border-color 0.2s, box-shadow 0.2s;
          outline: none;
          width: 100%;
          box-sizing: border-box;
          background: #f8fafc;
          color: #1e293b;
        }

        .login-form .form-input:focus {
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
          background: #ffffff;
        }

        .login-form .form-input:disabled {
          background: #f1f5f9;
          cursor: not-allowed;
          color: #94a3b8;
        }

        .login-form .form-input::placeholder {
          color: #94a3b8;
        }

        .password-input-wrapper {
          position: relative;
          display: flex;
          align-items: center;
        }

        .password-input-wrapper .form-input {
          padding-right: 44px;
        }

        .password-toggle {
          position: absolute;
          right: 12px;
          background: none;
          border: none;
          color: #94a3b8;
          cursor: pointer;
          padding: 4px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 4px;
          transition: all 0.2s;
        }

        .password-toggle:hover {
          color: #475569;
          background: #e2e8f0;
        }

        .login-button {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 14px 24px;
          background: #2563eb;
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
          margin-top: 4px;
        }

        .login-button:hover:not(:disabled) {
          background: #1d4ed8;
          box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        }

        .login-button:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }

        .login-button .spin {
          animation: spin 1s linear infinite;
        }

        .login-footer {
          text-align: center;
          margin-top: 24px;
          padding-top: 24px;
          border-top: 1px solid #e2e8f0;
        }

        .login-footer p {
          font-size: 13px;
          color: #94a3b8;
          margin: 0;
        }

        @keyframes spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  );
};

export default Login;
