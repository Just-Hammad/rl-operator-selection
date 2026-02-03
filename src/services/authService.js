import { supabase } from '../lib/supabaseClient';

/**
 * Sign in with email and password
 * @param {string} email 
 * @param {string} password 
 * @returns {Promise<{user: object, session: object, error: object}>}
 */
export const signIn = async (email, password) => {
  try {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      console.error('[Auth] Sign in error:', error.message);
      return { user: null, session: null, error };
    }

    console.log('[Auth] Sign in successful:', data.user?.email);
    return { user: data.user, session: data.session, error: null };
  } catch (error) {
    console.error('[Auth] Unexpected sign in error:', error);
    return { user: null, session: null, error };
  }
};

/**
 * Sign out the current user
 * @returns {Promise<{error: object}>}
 */
export const signOut = async () => {
  try {
    const { error } = await supabase.auth.signOut();
    
    if (error) {
      console.error('[Auth] Sign out error:', error.message);
      return { error };
    }

    console.log('[Auth] Sign out successful');
    return { error: null };
  } catch (error) {
    console.error('[Auth] Unexpected sign out error:', error);
    return { error };
  }
};

/**
 * Get the current session
 * @returns {Promise<{session: object, error: object}>}
 */
export const getSession = async () => {
  try {
    const { data, error } = await supabase.auth.getSession();
    
    if (error) {
      console.error('[Auth] Get session error:', error.message);
      return { session: null, error };
    }

    return { session: data.session, error: null };
  } catch (error) {
    console.error('[Auth] Unexpected get session error:', error);
    return { session: null, error };
  }
};

/**
 * Get the current user
 * @returns {Promise<{user: object, error: object}>}
 */
export const getUser = async () => {
  try {
    const { data, error } = await supabase.auth.getUser();
    
    if (error) {
      console.error('[Auth] Get user error:', error.message);
      return { user: null, error };
    }

    return { user: data.user, error: null };
  } catch (error) {
    console.error('[Auth] Unexpected get user error:', error);
    return { user: null, error };
  }
};

/**
 * Check if the current user is an admin by checking the admin_users table
 * @returns {Promise<boolean>}
 */
export const checkIsAdmin = async () => {
  try {
    const { data: { user } } = await supabase.auth.getUser();
    
    if (!user) {
      return false;
    }

    // Check if user exists in admin_users table
    const { data, error } = await supabase
      .from('admin_users')
      .select('id')
      .eq('user_id', user.id)
      .single();

    if (error) {
      // If error is "no rows returned", user is not admin
      if (error.code === 'PGRST116') {
        return false;
      }
      console.error('[Auth] Check admin error:', error.message);
      return false;
    }

    return !!data;
  } catch (error) {
    console.error('[Auth] Unexpected check admin error:', error);
    return false;
  }
};

/**
 * Subscribe to auth state changes
 * @param {function} callback - Callback function that receives (event, session)
 * @returns {function} Unsubscribe function
 */
export const onAuthStateChange = (callback) => {
  const { data: { subscription } } = supabase.auth.onAuthStateChange(callback);
  return () => subscription.unsubscribe();
};
