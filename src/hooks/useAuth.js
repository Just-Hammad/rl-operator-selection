import { useContext } from 'react';
import AuthContext from '../contexts/AuthContext';

/**
 * Custom hook to access auth context
 * Must be used within an AuthProvider
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
