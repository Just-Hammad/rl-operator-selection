import React, { createContext, useState, useEffect } from 'react';
import { 
  signIn as authSignIn, 
  signOut as authSignOut, 
  getSession, 
  checkIsAdmin,
  onAuthStateChange 
} from '../services/authService';
import { fetchElevenLabsApiKey } from '../services/apiKeyService';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [elevenLabsApiKey, setElevenLabsApiKey] = useState('');
  const [authError, setAuthError] = useState(null);

  // Fetch API key after successful admin authentication
  const fetchApiKeyForAdmin = async () => {
    try {
      const { apiKey, error } = await fetchElevenLabsApiKey();
      if (error) {
        console.error('[AuthContext] Failed to fetch ElevenLabs API key:', error);
        return;
      }
      if (apiKey) {
        setElevenLabsApiKey(apiKey);
        // Also store in sessionStorage for compatibility with existing code
        sessionStorage.setItem('xi-api-key', apiKey);
        console.log('[AuthContext] ElevenLabs API key loaded successfully');
      }
    } catch (error) {
      console.error('[AuthContext] Error fetching API key:', error);
    }
  };

  // Initialize auth state on mount
  useEffect(() => {
    const initializeAuth = async () => {
      setIsLoading(true);
      try {
        const { session: currentSession } = await getSession();
        
        if (currentSession) {
          setSession(currentSession);
          setUser(currentSession.user);
          
          // Check if user is admin
          const adminStatus = await checkIsAdmin();
          setIsAdmin(adminStatus);
          
          if (adminStatus) {
            await fetchApiKeyForAdmin();
          }
        }
      } catch (error) {
        console.error('[AuthContext] Error initializing auth:', error);
        setAuthError(error);
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();

    // Subscribe to auth state changes
    const unsubscribe = onAuthStateChange(async (event, newSession) => {
      console.log('[AuthContext] Auth state changed:', event);
      
      if (event === 'SIGNED_IN' && newSession) {
        setSession(newSession);
        setUser(newSession.user);
        
        const adminStatus = await checkIsAdmin();
        setIsAdmin(adminStatus);
        
        if (adminStatus) {
          await fetchApiKeyForAdmin();
        }
      } else if (event === 'SIGNED_OUT') {
        setSession(null);
        setUser(null);
        setIsAdmin(false);
        setElevenLabsApiKey('');
        sessionStorage.removeItem('xi-api-key');
      } else if (event === 'TOKEN_REFRESHED' && newSession) {
        setSession(newSession);
      }
    });

    return () => unsubscribe();
  }, []);

  // Sign in function
  const signIn = async (email, password) => {
    setAuthError(null);
    try {
      const { user: signedInUser, session: newSession, error } = await authSignIn(email, password);
      
      if (error) {
        setAuthError(error.message || 'Failed to sign in');
        return { success: false, error: error.message };
      }

      // Check if user is admin
      const adminStatus = await checkIsAdmin();
      
      if (!adminStatus) {
        // Not an admin - sign them out
        await authSignOut();
        const errorMsg = 'Access denied. Admin privileges required.';
        setAuthError(errorMsg);
        return { success: false, error: errorMsg };
      }

      setUser(signedInUser);
      setSession(newSession);
      setIsAdmin(true);
      
      // Fetch API key for admin
      await fetchApiKeyForAdmin();
      
      return { success: true, error: null };
    } catch (error) {
      console.error('[AuthContext] Sign in error:', error);
      const errorMsg = error.message || 'An unexpected error occurred';
      setAuthError(errorMsg);
      return { success: false, error: errorMsg };
    }
  };

  // Sign out function
  const signOut = async () => {
    try {
      await authSignOut();
      setUser(null);
      setSession(null);
      setIsAdmin(false);
      setElevenLabsApiKey('');
      setAuthError(null);
      sessionStorage.removeItem('xi-api-key');
      sessionStorage.removeItem('xi-agent-id');
      return { success: true, error: null };
    } catch (error) {
      console.error('[AuthContext] Sign out error:', error);
      return { success: false, error: error.message };
    }
  };

  // Clear auth error
  const clearError = () => {
    setAuthError(null);
  };

  const value = {
    user,
    session,
    isAdmin,
    isLoading,
    elevenLabsApiKey,
    authError,
    signIn,
    signOut,
    clearError,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
