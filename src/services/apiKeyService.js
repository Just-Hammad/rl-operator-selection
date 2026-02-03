import { supabase } from '../lib/supabaseClient';

/**
 * Fetch an API key by name from the api_keys table
 * Only works for authenticated admin users (RLS protected)
 * @param {string} keyName - The name of the API key (e.g., 'elevenlabs')
 * @returns {Promise<{apiKey: string | null, error: object | null}>}
 */
export const fetchApiKey = async (keyName) => {
  try {
    const { data, error } = await supabase
      .from('api_keys')
      .select('api_key')
      .eq('key_name', keyName)
      .single();

    if (error) {
      console.error(`[API Keys] Error fetching ${keyName}:`, error.message);
      return { apiKey: null, error };
    }

    console.log(`[API Keys] Successfully fetched ${keyName} key`);
    return { apiKey: data.api_key, error: null };
  } catch (error) {
    console.error(`[API Keys] Unexpected error fetching ${keyName}:`, error);
    return { apiKey: null, error };
  }
};

/**
 * Fetch the ElevenLabs API key
 * Convenience function that wraps fetchApiKey
 * @returns {Promise<{apiKey: string | null, error: object | null}>}
 */
export const fetchElevenLabsApiKey = async () => {
  return fetchApiKey('elevenlabs');
};

/**
 * Fetch multiple API keys at once
 * @param {string[]} keyNames - Array of key names to fetch
 * @returns {Promise<{keys: object, errors: object[]}>}
 */
export const fetchApiKeys = async (keyNames) => {
  try {
    const { data, error } = await supabase
      .from('api_keys')
      .select('key_name, api_key')
      .in('key_name', keyNames);

    if (error) {
      console.error('[API Keys] Error fetching multiple keys:', error.message);
      return { keys: {}, errors: [error] };
    }

    const keys = {};
    data.forEach(row => {
      keys[row.key_name] = row.api_key;
    });

    console.log(`[API Keys] Successfully fetched ${Object.keys(keys).length} keys`);
    return { keys, errors: [] };
  } catch (error) {
    console.error('[API Keys] Unexpected error fetching multiple keys:', error);
    return { keys: {}, errors: [error] };
  }
};
