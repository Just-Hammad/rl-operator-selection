import { supabase } from '../lib/supabaseClient';
import { API_CONFIG } from '../utils/route';

const API_BASE_URL = `${API_CONFIG.BASE_URL}/api/v1`;

const MEMORY_CACHE_DURATION = 8000;
const memoryCache = {
  global: { data: null, timestamp: 0 }
};

// NOTE: fetchSessionMemories has been removed as it used the deprecated get_session_memories RPC
// Session memories are now handled through the chat messages system

export const fetchGlobalMemories = async (userId) => {
  const now = Date.now();

  if (memoryCache.global.data && (now - memoryCache.global.timestamp) < MEMORY_CACHE_DURATION) {
    return memoryCache.global.data;
  }

  try {
    console.log('[API GLOBAL] Fetching memories for:', { userId });

    const response = await fetch(`${API_BASE_URL}/memories/global`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId })
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch global memories: ${response.statusText}`);
    }

    const data = await response.json();
    console.log('[API GLOBAL] Raw response:', data);

    const memories = data.memories ? data.memories.map(item => ({
      id: item.id,
      memory: item.content,
      metadata: item.metadata || {},
      created_at: item.created_at
    })) : [];

    console.log('[API GLOBAL] Processed memories:', memories.length);
    memories.forEach((mem, idx) => {
      console.log(`[API GLOBAL] [${idx + 1}]`, mem.memory?.substring(0, 100));
    });

    const result = {
      success: true,
      user_id: userId,
      count: memories.length,
      memories: memories
    };

    memoryCache.global = {
      data: result,
      timestamp: now
    };

    return result;
  } catch (error) {
    console.error('[Memory Fetch] Error fetching global memories:', error);
    return {
      success: false,
      user_id: userId,
      count: 0,
      memories: []
    };
  }
};

export const clearMemoryCache = () => {
  memoryCache.global = { data: null, timestamp: 0 };
};

export const deleteSessionMemories = async (sessionId, userId) => {
  try {
    console.log('[DELETE] Session memories delete functionality not implemented with Supabase RPC');
    clearMemoryCache();
    return { success: true, message: 'Cache cleared' };
  } catch (error) {
    console.error('Error deleting session memories:', error);
    throw error;
  }
};

export const deleteMemoryById = async (memoryId) => {
  try {
    console.log('[DELETE] Deleting memory by ID:', memoryId);

    const response = await fetch(`${API_BASE_URL}/memories/memory`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memory_id: memoryId })
    });

    if (!response.ok) {
      throw new Error(`Failed to delete memory: ${response.statusText}`);
    }

    const data = await response.json();
    console.log('[DELETE] Delete result:', data);

    clearMemoryCache();

    return {
      success: data.success,
      message: data.message
    };
  } catch (error) {
    console.error('[DELETE] Error deleting memory by ID:', error);
    throw error;
  }
};

