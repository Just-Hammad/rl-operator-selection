import React, { useEffect, useState } from 'react';

const Toast = ({ message, onClose, duration = 3000 }) => {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(onClose, 200); // Wait for fade out animation
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const handleClose = () => {
    setIsVisible(false);
    setTimeout(onClose, 200);
  };

  return (
    <div className={`toast-container ${isVisible ? 'toast-visible' : 'toast-hidden'}`}>
      <div className="toast-content">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="toast-icon"
        >
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
          <line x1="12" y1="8" x2="12" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          <circle cx="12" cy="16" r="1" fill="currentColor" />
        </svg>
        <p className="toast-message">{message}</p>
        <button
          onClick={handleClose}
          className="toast-close-button"
          aria-label="Close notification"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 16 16"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M12 4L4 12M4 4L12 12"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      <style>{`
        .toast-container {
          position: fixed;
          top: 24px;
          right: 24px;
          z-index: 100;
          transition: all 0.2s ease-out;
        }

        .toast-visible {
          opacity: 1;
          transform: translateY(0);
        }

        .toast-hidden {
          opacity: 0;
          transform: translateY(-10px);
        }

        .toast-content {
          display: flex;
          align-items: center;
          gap: 12px;
          background: white;
          border: 1px solid #e2e8f0;
          border-left: 3px solid #3b82f6;
          border-radius: 8px;
          padding: 14px 16px;
          box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
          min-width: 320px;
          max-width: 420px;
        }

        .toast-icon {
          color: #3b82f6;
          flex-shrink: 0;
        }

        .toast-message {
          flex: 1;
          font-size: 14px;
          color: #1e293b;
          margin: 0;
          line-height: 1.5;
        }

        .toast-close-button {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 24px;
          height: 24px;
          padding: 0;
          aspect-ratio: 1 / 1;
          border-radius: 50%;
          border: 1px solid #e2e8f0;
          background: white;
          color: #64748b;
          cursor: pointer;
          transition: all 0.2s;
          flex-shrink: 0;
          box-sizing: border-box;
        }

        .toast-close-button:hover {
          background: #f8fafc;
          color: #1e293b;
          border-color: #cbd5e1;
        }

        .toast-close-button svg {
          width: 12px;
          height: 12px;
          display: block;
          flex-shrink: 0;
        }
      `}</style>
    </div>
  );
};

export default Toast;
