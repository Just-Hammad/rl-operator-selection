import { createClient } from '@supabase/supabase-js';
import { config } from './supabaseConfig';

let clientInstance = null;

export function getSupabaseClient() {
  if (!clientInstance) {
    clientInstance = createClient(config.supabaseUrl, config.supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
        storageKey: 'artsensei-admin-auth',
        storage: localStorage,
      }
    });
  }
  return clientInstance;
}

export const supabase = getSupabaseClient();
