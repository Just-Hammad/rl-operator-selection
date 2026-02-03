import React from 'react';
const SignOutDialog = ({ isOpen, onClose, onConfirm }) => {
  if (!isOpen) return null;

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-content" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <div className="dialog-header-content">
            <h2 className="dialog-title">Sign Out</h2>
            <p className="dialog-description">
              Are you sure you want to sign out? This will end your current session.
            </p>
          </div>
          <button
            onClick={onClose}
            className="dialog-close-button"
            aria-label="Close dialog"
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

        <div className="dialog-footer">
          <button
            type="button"
            onClick={onClose}
            className="dialog-button dialog-button-cancel"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="dialog-button dialog-button-confirm"
          >
            Sign Out
          </button>
        </div>
      </div>

      <style>{`
        .dialog-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 50;
          animation: fadeIn 0.2s ease-out;
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        .dialog-content {
          background: white;
          border-radius: 12px;
          border: 1px solid #e2e8f0;
          box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
          width: 90%;
          max-width: 420px;
          animation: slideUp 0.2s ease-out;
        }

        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .dialog-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          padding: 24px 24px 20px 24px;
          gap: 16px;
        }

        .dialog-header-content {
          flex: 1;
        }

        .dialog-title {
          font-size: 18px;
          font-weight: 600;
          color: #1e293b;
          margin: 0 0 8px 0;
        }

        .dialog-description {
          font-size: 14px;
          color: #64748b;
          margin: 0;
          line-height: 1.5;
        }

        .dialog-close-button {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 25px;
          height: 25px;
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
          box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
        }

        .dialog-close-button:hover {
          background: #f8fafc;
          color: #1e293b;
          border-color: #cbd5e1;
          box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        }

        .dialog-close-button svg {
          width: 12px;
          height: 12px;
          display: block;
          flex-shrink: 0;
        }

        .dialog-footer {
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 12px;
          padding: 16px 24px;
          background: #f8fafc;
          border-top: 1px solid #e2e8f0;
          border-radius: 0 0 12px 12px;
        }

        .dialog-button {
          padding: 10px 20px;
          font-size: 14px;
          font-weight: 600;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s;
          border: none;
        }

        .dialog-button-cancel {
          background: white;
          color: #475569;
          border: 1px solid #e2e8f0;
        }

        .dialog-button-cancel:hover {
          background: #f8fafc;
          border-color: #cbd5e1;
        }

        .dialog-button-confirm {
          background: #1e293b;
          color: white;
        }

        .dialog-button-confirm:hover {
          background: #0f172a;
        }
      `}</style>
    </div>
  );
};

export default SignOutDialog;
