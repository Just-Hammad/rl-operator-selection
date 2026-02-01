import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useConversation } from '@elevenlabs/react';
import { Send, Image as ImageIcon, Settings, Save, RefreshCw, BookOpen, CheckSquare, Square, Edit2, Trash2, ArrowLeft, Eye, EyeOff, Loader2 } from 'lucide-react';
import './App.css';
import MemoryViewer from './components/MemoryViewer';
import { fetchGlobalMemories, clearMemoryCache, deleteMemoryById } from './services/memoryService';
import { getChatMessagesBySessionId, getRawChatMessages } from './services/chatService';
import { addMessageToSupabase } from './services/messageService';
import { fetchFirstMessage } from './services/greetingService';
import { TEST_USER_ID, agents } from './constants';
import { formatGlobalContext } from './utils';
import { API_CONFIG } from './utils/route';
import { getArtworkByBasename } from './utils/artworkInfo';
import { createNewSession, saveSessionToStorage, getSessionFromStorage } from './services/sessionManager';

// Default Config
const DEFAULT_BACKEND = API_CONFIG.BASE_URL;
// NOTE: For Admin updates, we go direct to ElevenLabs API to avoid needing backend endpoints for it


function App() {
  // --- STATE ---
  const [backendUrl, setBackendUrl] = useState(DEFAULT_BACKEND);
  const [apiKey, setApiKey] = useState(sessionStorage.getItem("xi-api-key") || import.meta.env.VITE_ELEVENLABS_API_KEY || "");
  const [agentId, setAgentId] = useState(sessionStorage.getItem("xi-agent-id") || import.meta.env.VITE_AGENT_ID || "");
  const [savedApiKey, setSavedApiKey] = useState("");
  const [savedAgentId, setSavedAgentId] = useState("");
  const [configAgentName, setConfigAgentName] = useState("");
  const [isFetchingAgentName, setIsFetchingAgentName] = useState(false);
  const [isHoveringAgentName, setIsHoveringAgentName] = useState(false);

  // UI State
  const [showApiKey, setShowApiKey] = useState(false);

  // Chat State
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState("");
  const [connectionStatus, setConnectionStatus] = useState("disconnected");
  const [isWaitingForResponse, setIsWaitingForResponse] = useState(false);
  const [agentName, setAgentName] = useState("");
  const messagesEndRef = useRef(null);

  // Admin State
  const [systemPrompt, setSystemPrompt] = useState("");

  const [availableKBs, setAvailableKBs] = useState([]);
  const [selectedKBMap, setSelectedKBMap] = useState({});
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [isSavingConfig, setIsSavingConfig] = useState(false);

  const [loadedSystemPrompt, setLoadedSystemPrompt] = useState("");
  const [loadedKBMap, setLoadedKBMap] = useState({});

  const [editingKB, setEditingKB] = useState(null);
  const [kbContent, setKbContent] = useState("");
  const [isSavingKB, setIsSavingKB] = useState(false);

  const [memoryExpanded, setMemoryExpanded] = useState(false);

  const [globalMemories, setGlobalMemories] = useState([]);
  const [isLoadingMemories, setIsLoadingMemories] = useState(false);
  const [hasLoadedMemoriesOnce, setHasLoadedMemoriesOnce] = useState(false);

  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [isInitializingSession, setIsInitializingSession] = useState(true);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [dynamicFirstMessage, setDynamicFirstMessage] = useState(null);
  const [isFetchingFirstMessage, setIsFetchingFirstMessage] = useState(false);

  // Image Upload State
  const [uploadedImages, setUploadedImages] = useState([]);
  const [isUploadingImage, setIsUploadingImage] = useState(false);
  const [isDeletingImage, setIsDeletingImage] = useState(false);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const fileInputRef = useRef(null);
  const chatPanelRef = useRef(null);

  // --- ELEVENLABS HOOK ---
  const conversation = useConversation({
    onConnect: () => {
      setConnectionStatus("connected");
      addSystemMessage("Agent Connected!");
    },
    onDisconnect: () => {
      setConnectionStatus("disconnected");
      addSystemMessage("Agent Disconnected.");
    },
    onMessage: (message) => {
      console.log("Msg:", message);
      const role = message.source === 'user' ? 'user' : 'assistant';
      const text = message.message || "";
      addMessage(role, text);
      if (role === 'assistant') {
        setIsWaitingForResponse(false);
      }
    },
    onError: (err) => {
      console.error(err);
      addSystemMessage(`Error: ${err.message}`);
      setConnectionStatus("error");
    }
  });

  // --- HELPERS ---
  const addMessage = async (role, content, attachments = []) => {
    // Add to local state immediately
    setMessages(prev => [...prev, { role, content, attachments, timestamp: new Date() }]);

    // Save to Supabase (fire and forget)
    if (currentSessionId && role !== 'system') {
      addMessageToSupabase(currentSessionId, {
        role,
        content,
        attachments,
      }).then(result => {
        if (result.success) {
          console.log(`[App] Message saved to Supabase:`, result.message?.id);
        } else {
          console.error(`[App] Failed to save message to Supabase:`, result.error);
        }
      }).catch(err => {
        console.error(`[App] Error saving message to Supabase:`, err);
      });
    }
  };

  const addSystemMessage = (text) => {
    setMessages(prev => [...prev, { role: 'system', content: text, timestamp: new Date() }]);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const uploadImageToBackend = async (file) => {
    const formData = new FormData();
    formData.append('image', file);
    formData.append('conversation_id', currentSessionId);
    formData.append('user_id', TEST_USER_ID);

    const response = await axios.post(`${backendUrl}${API_CONFIG.ENDPOINTS.IMAGES.UPLOAD}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  };

  const handleFileSelect = async (files) => {
    if (!files || files.length === 0) return;

    setIsUploadingImage(true);
    try {
      const uploadPromises = Array.from(files)
        .filter(file => file.type.startsWith('image/'))
        .map(async (file) => {
          const result = await uploadImageToBackend(file);
          return {
            localUrl: URL.createObjectURL(file),
            serverUrl: result.public_image_url,
            fileName: file.name
          };
        });

      const newImages = await Promise.all(uploadPromises);
      setUploadedImages(prev => [...prev, ...newImages]);
    } catch (error) {
      console.error('Failed to upload images:', error);
      addSystemMessage('Failed to upload images. Please try again.');
    } finally {
      setIsUploadingImage(false);
    }
  };

  const handleImageButtonClick = () => {
    if (connectionStatus === 'connected') {
      fileInputRef.current?.click();
    }
  };

  const handleFileInputChange = (e) => {
    handleFileSelect(e.target.files);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (connectionStatus === 'connected') {
      setIsDraggingOver(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX;
    const y = e.clientY;
    if (x <= rect.left || x >= rect.right || y <= rect.top || y >= rect.bottom) {
      setIsDraggingOver(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);
    if (connectionStatus === 'connected') {
      handleFileSelect(e.dataTransfer.files);
    }
  };

  const removeUploadedImage = async (index) => {
    const imageToRemove = uploadedImages[index];

    setUploadedImages(prev => prev.filter((_, i) => i !== index));

    if (imageToRemove?.serverUrl && currentSessionId) {
      setIsDeletingImage(true);
      try {
        const deleteFormData = new FormData();
        deleteFormData.append('image_url', imageToRemove.serverUrl);
        deleteFormData.append('conversation_id', currentSessionId);
        deleteFormData.append('user_id', TEST_USER_ID);

        await axios.post(`${backendUrl}${API_CONFIG.ENDPOINTS.IMAGES.DELETE}`, deleteFormData);
        console.log('[App] Image deleted from backend:', imageToRemove.serverUrl);
      } catch (error) {
        console.error('[App] Failed to delete image from backend:', error);
      } finally {
        setIsDeletingImage(false);
      }
    }
  };

  // Client Tools State
  const [activeImage, setActiveImage] = useState(null);
  const [highlight, setHighlight] = useState(null);

  const loadMemories = async () => {
    if (!currentSessionId) {
      return;
    }

    if (!hasLoadedMemoriesOnce) {
      setIsLoadingMemories(true);
    }
    try {
      const globalData = await fetchGlobalMemories(TEST_USER_ID);
      setGlobalMemories(globalData.memories || []);

      if (!hasLoadedMemoriesOnce) {
        setHasLoadedMemoriesOnce(true);
      }
    } catch (error) {
      console.error('Failed to load memories:', error);
    } finally {
      if (!hasLoadedMemoriesOnce) {
        setIsLoadingMemories(false);
      }
    }
  };

  const handleDeleteMemory = async (memoryId) => {
    try {
      console.log('[APP] Deleting memory:', memoryId);

      const result = await deleteMemoryById(memoryId);
      console.log('[APP] Delete memory response:', result);

      if (result.success) {
        setGlobalMemories(prev => prev.filter(m => m.id !== memoryId));
        await loadMemories();
      }

      return result;
    } catch (error) {
      console.error('[APP] Failed to delete memory:', error);
      throw error;
    }
  };

  // --- ACTIONS ---
  const fetchAgentName = async () => {
    try {
      console.log(`[Agent Info] Fetching agent details for agent ID: ${agentId}`);
      const response = await axios.get(`${API_CONFIG.ELEVENLABS_BASE_URL}${API_CONFIG.ENDPOINTS.ELEVENLABS.AGENTS}/${agentId}`, {
        headers: { 'xi-api-key': apiKey }
      });

      const agentData = response.data;
      let fetchedName = agentData.name;

      if (!fetchedName) {
        const localAgent = agents.find(agent => agent.id === agentId);
        if (localAgent) {
          fetchedName = localAgent.name;
          console.log(`[Agent Info] Using local agent name: ${fetchedName}`);
        } else fetchedName = "Unknown Agent";

      } else
        console.log(`[Agent Info] Successfully fetched agent name from API: ${fetchedName}`);


      console.log(`[Agent Info] Full agent data:`, agentData);

      setAgentName(fetchedName);
      return fetchedName;
    } catch (error) {
      console.error(`[Agent Info] Failed to fetch agent details:`, error);
      const localAgent = agents.find(agent => agent.id === agentId);
      const fallbackName = localAgent ? localAgent.name : "Unknown Agent";
      if (localAgent) {
        console.log(`[Agent Info] Using local agent name after API error: ${fallbackName}`);
      }
      setAgentName(fallbackName);
      return fallbackName;
    }
  };

  const handleConnect = async () => {
    if (!agentId) return alert("Please enter an Agent ID first");
    if (!currentSessionId) return alert("Session not initialized. Please wait or create a new session.");

    const storedSessionId = localStorage.getItem('artsensei_session_id');
    if (!storedSessionId) {
      return alert("No active session found in storage. Please create a new session first.");
    }

    setConnectionStatus("connecting");
    try {
      console.log(`[Connect] Starting connection process for agent: ${agentId}`);

      // Parallel fetch: agent name, signed URL, global memories, chat messages
      setIsFetchingFirstMessage(true);
      console.log(`[Connect] Starting paraltch for connection data...`);

      console.log(`[Connect] Fetching data for session: ${currentSessionId}`);

      // Prepare FormData for cache revalidation
      const cacheFormData = new FormData();
      cacheFormData.append('conversation_id', currentSessionId);
      cacheFormData.append('user_id', TEST_USER_ID);

      const [
        fetchedAgentName,
        signedUrlResp,
        globalData,
        chatMessagesResult,
        _cacheRevalidation
      ] = await Promise.all([
        fetchAgentName(),
        axios.get(`${backendUrl}${API_CONFIG.ENDPOINTS.ELEVENLABS.SIGNED_URL}?text_mode=true`, {
          headers: {
            'xi-api-key': apiKey,
            'xi-agent-id': agentId
          }
        }),
        fetchGlobalMemories(TEST_USER_ID).catch(err => {
          console.error(`[Connect] Failed to fetch global memories:`, err);
          return { memories: [] };
        }),
        getChatMessagesBySessionId(currentSessionId).catch(err => {
          console.error(`[Connect] Failed to fetch chat messages:`, err);
          return { data: [] };
        }),
        axios.post(`${backendUrl}${API_CONFIG.ENDPOINTS.IMAGES.REVALIDATE_CACHE}`, cacheFormData).catch(err => {
          console.error(`[Connect] Failed to revalidate image cache:`, err);
          return { data: { images: [] } };
        })
      ]);

      const { signedUrl: url } = signedUrlResp.data;
      console.log(`[Connect] Signed URL obtained successfully`);

      const globalContext = formatGlobalContext(globalData);
      const chatMessages = chatMessagesResult.data || [];

      console.log(`[Connect] Data loaded:`, {
        globalCount: globalData?.memories?.length || 0,
        chatMessagesCount: chatMessages.length
      });

      // Fetch dynamic first message only if session has 0 messages
      let firstMessage = null;
      if (chatMessages.length === 0) {
        console.log(`[Connect] No existing messages - fetching first message...`);
        try {
          firstMessage = await fetchFirstMessage(TEST_USER_ID, "there", globalContext);
          if (firstMessage) {
            setDynamicFirstMessage(firstMessage);
            console.log(`[Connect] Dynamic first message:`, firstMessage);
          }
        } catch (fmErr) {
          console.error(`[Connect] Failed to fetch first message:`, fmErr);
        }
      } else {
        console.log(`[Connect] Skipping first message - session has ${chatMessages.length} existing messages`);
        setDynamicFirstMessage(null);
        firstMessage = null;
      }
      setIsFetchingFirstMessage(false);

      // Start the conversation session
      console.log(`[Connect] Starting conversation session...`);

      console.log("[CONNECTIONS] globalContext=> ", globalContext);
      console.log("[CONNECTIONS] chatMessages=> ", chatMessages);

      const sessionOptions = {
        signedUrl: url,
        connectionType: "websocket",
        customLlmExtraBody: {
          chatId: currentSessionId,
          userId: TEST_USER_ID,
          globalMemories: globalContext || "No global memories available for this user.",
          chatMessages: chatMessages,
          testing: true,
        },
        dynamicVariables: {
          first_name: "there",
        },
        clientTools: {
          showImageOnScreen: async ({ imagePath }) => {
            console.log("[ClientTool] showImageOnScreen:", imagePath);

            const filename = imagePath;
            const artwork = getArtworkByBasename(filename);

            if (artwork?.public_url) {
              setActiveImage({ url: artwork.public_url, title: imagePath, artwork });
              addSystemMessage(`📷 Showing Image: ${imagePath}`);
              return "Image found successfully";
            } else {
              console.log("[ClientTool] No public_url available for:", imagePath);
              addSystemMessage(`⚠️ Image not available: ${imagePath}`);
              return `The image at ${imagePath} is not available in the artwork database. Please apologize and show a different example.`;
            }
          },
          pointObjectInImage: async ({ query }) => {
            console.log("[ClientTool] pointObjectInImage:", query);
            addSystemMessage(`🔍 Pointing at object: ${query}`);

            if (!activeImage) {
              return "No active image to point at.";
            }

            try {
              const response = await axios.post(`${backendUrl}${API_CONFIG.ENDPOINTS.VISION.POINT}`, {
                filename: activeImage.title,
                object: query,
                max_points: 1
              }, {
                headers: { 'xi-api-key': apiKey }
              });

              const { points, count } = response.data;
              if (count > 0 && points[0]) {
                const { x, y } = points[0];
                addSystemMessage(`✅ Found ${query} at [${x}, ${y}]`);
                setHighlight({ x, y, label: query });
                setTimeout(() => setHighlight(null), 5000);
                return `Found ${query} at coordinates ${x},${y}`;
              } else {
                return `Could not find ${query} in the image.`;
              }
            } catch (err) {
              console.error("Vision API Error:", err);
              return `Failed to point: ${err.message}`;
            }
          }
        }
      };

      // Always set overrides - use empty string to suppress default greeting when resuming
      sessionOptions.overrides = {
        agent: {
          firstMessage: firstMessage || "",
        },
      };

      await conversation.startSession(sessionOptions);

      console.log(`[Connect] Session started successfully with agent: ${fetchedAgentName}`);

    } catch (err) {
      console.error("[Connect] Error:", err);
      setConnectionStatus("error");
      addSystemMessage(`Connection Failed: ${err.message}`);
      setAgentName(""); // Clear agent name on error
    }
  };

  const handleDisconnect = async () => {
    console.log(`[Disconnect] Disconnecting from agent: ${agentName}`);
    await conversation.endSession();
    setActiveImage(null);
    setAgentName("");
    setIsWaitingForResponse(false);
    console.log(`[Disconnect] Successfully disconnected`);
  };

  const handleSend = async () => {
    if (!inputText.trim() && uploadedImages.length === 0) return;
    if (connectionStatus !== 'connected') {
      console.error("Cannot send message: Not connected to ElevenLabs");
      return;
    }

    try {
      const messageContent = inputText.trim() || "[Image(s) uploaded]";
      const imageUrls = uploadedImages.map(img => img.serverUrl);

      // Pass attachments to the message
      addMessage('user', messageContent, uploadedImages);
      setInputText("");
      setUploadedImages([]);
      setIsWaitingForResponse(true);

      if (imageUrls.length > 0) {
        const messageWithImages = `${messageContent}\n\nImages: ${imageUrls.join(', ')}`;
        await conversation.sendUserMessage(messageWithImages);
      } else {
        await conversation.sendUserMessage(messageContent);
      }
    } catch (error) {
      console.error("Failed to send message:", error);
      addSystemMessage(`Failed to send message: ${error.message}`);
      setIsWaitingForResponse(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      if (connectionStatus === 'connected' && !isUploadingImage && (inputText.trim() || uploadedImages.length > 0)) {
        handleSend();
      }
    }
  };

  // --- ADMIN & KB ACTIONS ---

  const loadConfig = async () => {
    if (!apiKey || !agentId) return;
    setIsLoadingConfig(true);
    try {
      console.log(`[DEBUG] Loading Config for Agent: ${agentId}`);
      console.log(`[DEBUG] Using API Key: ${apiKey ? apiKey.substring(0, 5) + "..." : "MISSING"}`);
      const agentResp = await axios.get(`${API_CONFIG.ELEVENLABS_BASE_URL}${API_CONFIG.ENDPOINTS.ELEVENLABS.AGENTS}/${agentId}`, {
        headers: { 'xi-api-key': apiKey }
      });
      const config = agentResp.data.conversation_config?.agent;
      const loadedPrompt = config?.prompt?.prompt || "";
      setSystemPrompt(loadedPrompt);
      setLoadedSystemPrompt(loadedPrompt);

      const currentKBs = config?.knowledge_base || [];
      const currentKBMap = {};
      currentKBs.forEach(kb => { currentKBMap[kb.id] = kb; });
      setSelectedKBMap(currentKBMap);
      setLoadedKBMap(currentKBMap);

      await refreshKBList();

    } catch (err) {
      console.error(`Failed to load config: ${err.message}`);
    } finally {
      setIsLoadingConfig(false);
    }
  };

  const refreshKBList = async () => {
    const kbResp = await axios.get(`${API_CONFIG.ELEVENLABS_BASE_URL}${API_CONFIG.ENDPOINTS.ELEVENLABS.KNOWLEDGE_BASE}?page_size=100`, {
      headers: { 'xi-api-key': apiKey }
    });
    setAvailableKBs(kbResp.data.documents || []);
  };

  const saveConfig = async () => {
    if (!apiKey || !agentId) return;

    setIsSavingConfig(true);
    try {
      const kbList = Object.values(selectedKBMap).map(kb => ({
        id: kb.id,
        name: kb.name,
        type: kb.type
      }));

      await axios.patch(`${API_CONFIG.ELEVENLABS_BASE_URL}${API_CONFIG.ENDPOINTS.ELEVENLABS.AGENTS}/${agentId}`, {
        conversation_config: {
          agent: {
            prompt: {
              prompt: systemPrompt,
              knowledge_base: kbList
            }
          }
        }
      }, {
        headers: { 'xi-api-key': apiKey, 'Content-Type': 'application/json' }
      });
      setLoadedSystemPrompt(systemPrompt);
      setLoadedKBMap(selectedKBMap);
      alert("Agent Configuration Saved!");
    } catch (err) {
      alert(`Save Failed: ${err.message}`);
    } finally {
      setIsSavingConfig(false);
    }
  };

  const toggleKB = (kb) => {
    setSelectedKBMap(prev => {
      const next = { ...prev };
      if (next[kb.id]) delete next[kb.id];
      else next[kb.id] = { id: kb.id, name: kb.name, type: kb.type };
      return next;
    });
  };

  // --- KB EDITING ---

  const handleEditKB = async (kb) => {
    setEditingKB(kb);
    setKbContent("Loading content...");
    try {
      const resp = await axios.get(`${API_CONFIG.ELEVENLABS_BASE_URL}${API_CONFIG.ENDPOINTS.ELEVENLABS.KNOWLEDGE_BASE}/${kb.id}`, {
        headers: { 'xi-api-key': apiKey }
      });
      const data = resp.data;
      if (data.extracted_inner_html) setKbContent(data.extracted_inner_html);
      else if (kb.type === 'url') setKbContent(data.url || "URL Document");
      else setKbContent("(Content not viewable via API)");
    } catch (e) {
      setKbContent("(Could not load content)");
    }
  };

  const handleRenameKB = async (id, newName) => {
    try {
      await axios.patch(`${API_CONFIG.ELEVENLABS_BASE_URL}${API_CONFIG.ENDPOINTS.ELEVENLABS.KNOWLEDGE_BASE}/${id}`, {
        name: newName
      }, {
        headers: { 'xi-api-key': apiKey }
      });
      alert("Renamed successfully!");
      // Update local state
      setSelectedKBMap(prev => {
        const next = { ...prev };
        if (next[id]) next[id].name = newName;
        return next;
      });
      refreshKBList();
    } catch (e) {
      alert("Failed to rename: " + e.message);
    }
  };

  const handleDeleteKB = async (id) => {
    if (!confirm("Are you sure you want to delete this Knowledge Base document? This cannot be undone.")) return;
    try {
      await axios.delete(`${API_CONFIG.ELEVENLABS_BASE_URL}${API_CONFIG.ENDPOINTS.ELEVENLABS.KNOWLEDGE_BASE}/${id}`, {
        headers: { 'xi-api-key': apiKey }
      });
      setSelectedKBMap(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setEditingKB(null);
      await refreshKBList();
    } catch (e) {
      alert("Failed to delete: " + e.message);
    }
  };



  const handleCreateNewSession = async () => {
    if (connectionStatus === 'connected') {
      return;
    }

    setIsCreatingSession(true);
    try {
      const result = await createNewSession(TEST_USER_ID);
      saveSessionToStorage(result.sessionId);
      setCurrentSessionId(result.sessionId);
      setMessages([]);
      setGlobalMemories([]);
      setHasLoadedMemoriesOnce(false);
      setDynamicFirstMessage(null);
      console.log('[New Session] Created:', result.sessionId);
    } catch (error) {
      console.error('[New Session] Failed to create:', error);
      alert('Failed to create new session. Please try again.');
    } finally {
      setIsCreatingSession(false);
    }
  };


  useEffect(() => {
    scrollToBottom();
  }, [messages, isWaitingForResponse]);

  useEffect(() => {
    const storedApiKey = sessionStorage.getItem("xi-api-key") || import.meta.env.VITE_ELEVENLABS_API_KEY || "";
    const storedAgentId = sessionStorage.getItem("xi-agent-id") || import.meta.env.VITE_AGENT_ID || "";
    setSavedApiKey(storedApiKey);
    setSavedAgentId(storedAgentId);
  }, []);

  useEffect(() => {
    setConfigAgentName("");

    if (!agentId || !apiKey) {
      setSystemPrompt("");
      setLoadedSystemPrompt("");
      setSelectedKBMap({});
      setLoadedKBMap({});
      setAvailableKBs([]);
      return;
    }

    const debounceTimer = setTimeout(async () => {
      setIsFetchingAgentName(true);
      try {
        const response = await axios.get(`${API_CONFIG.ELEVENLABS_BASE_URL}${API_CONFIG.ENDPOINTS.ELEVENLABS.AGENTS}/${agentId}`, {
          headers: { 'xi-api-key': apiKey }
        });
        const agentData = response.data;
        const fetchedName = agentData.name || "";
        setConfigAgentName(fetchedName);

        await loadConfig();
      } catch (error) {
        console.error('Failed to fetch agent name:', error);
        setConfigAgentName("");
      } finally {
        setIsFetchingAgentName(false);
      }
    }, 500);

    return () => clearTimeout(debounceTimer);
  }, [agentId, apiKey]);

  useEffect(() => {
    const initSession = async () => {
      setIsInitializingSession(true);
      try {
        const existingSessionId = getSessionFromStorage();

        if (existingSessionId) {
          console.log('[App] Found existing session:', existingSessionId);
          setCurrentSessionId(existingSessionId);

          const messagesResult = await getRawChatMessages(existingSessionId);
          if (messagesResult.data && messagesResult.data.length > 0) {
            setMessages(messagesResult.data);
            console.log('[App] Loaded', messagesResult.data.length, 'messages from existing session');
          }
        } else {
          console.log('[App] No existing session found');
        }
      } catch (error) {
        console.error('[App] Failed to initialize session:', error);
      } finally {
        setIsInitializingSession(false);
      }
    };

    initSession();
  }, []);

  useEffect(() => {
    if (!currentSessionId) {
      return;
    }

    loadMemories();

    const pollingInterval = setInterval(() => {
      loadMemories();
    }, 8000);

    return () => {
      clearInterval(pollingInterval);
      clearMemoryCache();
    };
  }, [currentSessionId]);

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isDraggingOver) {
        setIsDraggingOver(false);
      }
    };

    const handleWindowBlur = () => {
      setIsDraggingOver(false);
    };

    const handleDragEnd = () => {
      setIsDraggingOver(false);
    };

    window.addEventListener('keydown', handleEscape);
    window.addEventListener('blur', handleWindowBlur);
    window.addEventListener('dragend', handleDragEnd);
    document.addEventListener('dragleave', (e) => {
      if (e.clientX === 0 && e.clientY === 0) {
        setIsDraggingOver(false);
      }
    });

    return () => {
      window.removeEventListener('keydown', handleEscape);
      window.removeEventListener('blur', handleWindowBlur);
      window.removeEventListener('dragend', handleDragEnd);
    };
  }, [isDraggingOver]);

  return (
    <div className="app-container" onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        onChange={handleFileInputChange}
        style={{ display: 'none' }}
      />

      {isDraggingOver && (
        <div className="drag-overlay">
          <div className="drag-content">
            <ImageIcon size={64} strokeWidth={1.5} />
            <p>Drop images here</p>
          </div>
        </div>
      )}

      {/* COLUMN 1: CHAT (Left) */}
      <div className="panel chat-panel" ref={chatPanelRef}>
        <div className="header" style={{ flexWrap: 'wrap', gap: '8px' }}>
          <h2 className="header-title" style={{ minWidth: '0', flex: '1 1 auto', maxWidth: '100%' }}>
            <div className={`status-dot ${connectionStatus === 'connected' ? 'connected' : connectionStatus === 'connecting' ? 'connecting' : 'disconnected'}`} />
            {connectionStatus === 'connected' && agentName ? (
              <span className="agent-name-badge" style={{ wordBreak: 'break-word', whiteSpace: 'normal', maxWidth: '100%' }}>{agentName}</span>
            ) : (
              'Chat'
            )}
          </h2>
          <div className="actions" style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
            {connectionStatus !== 'connected' && (
              <button
                onClick={handleCreateNewSession}
                disabled={isCreatingSession || isInitializingSession}
                className="btn-secondary"
                title="Create New Session"
                style={{ whiteSpace: 'nowrap' }}
              >
                {isCreatingSession ? (
                  <>
                    <Loader2 size={14} className="spin" />
                    <span>Creating...</span>
                  </>
                ) : (
                  'New Session'
                )}
              </button>
            )}
            {connectionStatus !== 'connected' ? (
              <button onClick={handleConnect} disabled={connectionStatus === 'connecting' || !currentSessionId || isInitializingSession || isCreatingSession} className="btn-primary" style={{ whiteSpace: 'nowrap' }}>
                {connectionStatus === 'connecting' ? 'Connecting...' : 'Connect'}
              </button>
            ) : (
              <button onClick={handleDisconnect} className="btn-red" style={{ whiteSpace: 'nowrap' }}>Stop</button>
            )}
          </div>
        </div>

        <div className="messages-list">
          {messages.map((msg, i) => (
            <div key={i} className={`message-row ${msg.role}`}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '100%' }}>
                {msg.role === 'user' && msg.attachments && msg.attachments.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '8px', justifyContent: 'flex-end' }}>
                    {msg.attachments.map((attachment, idx) => (
                      <div
                        key={idx}
                        style={{
                          width: '60px',
                          height: '60px',
                          borderRadius: '8px',
                          overflow: 'hidden',
                          border: '2px solid #e2e8f0',
                          cursor: 'pointer',
                        }}
                      // onClick={() => {
                      //   const finalUrl = attachment.serverUrl || attachment.localUrl;
                      //   if (finalUrl) {
                      //     setActiveImage({ url: finalUrl, title: attachment.fileName || 'Uploaded Image' });
                      //   }
                      // }}
                      >
                        <img
                          src={attachment.localUrl || attachment.serverUrl}
                          alt={attachment.fileName || 'attachment'}
                          style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                          }}
                        />
                      </div>
                    ))}
                  </div>
                )}
                <div className={`message-bubble ${msg.role}`}>{msg.content}</div>
              </div>
            </div>
          ))}
          {isWaitingForResponse && (
            <div className="message-row assistant">
              <div className="marcel-loading">
                <span className="marcel-name">Marcel</span>
                <div className="loading-dots">
                  <span className="dot" style={{ animationDelay: '0ms' }}></span>
                  <span className="dot" style={{ animationDelay: '150ms' }}></span>
                  <span className="dot" style={{ animationDelay: '300ms' }}></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>



        {activeImage && (
          <div className="image-preview-overlay">
            <div className="image-card">
              <img src={activeImage.url} alt={activeImage.title} />
              {highlight && (
                <div style={{
                  position: 'absolute',
                  left: `${highlight.x * 100}%`,
                  top: `${highlight.y * 100}%`,
                  width: '20px',
                  height: '20px',
                  backgroundColor: 'rgba(255, 0, 0, 0.5)',
                  border: '2px solid red',
                  borderRadius: '50%',
                  transform: 'translate(-50%, -50%)',
                  pointerEvents: 'none',
                  boxShadow: '0 0 10px rgba(255,0,0,0.8)'
                }} />
              )}
              <div className="image-caption">{activeImage.title}</div>
              <button className="close-btn" onClick={() => setActiveImage(null)}>×</button>
            </div>
          </div>
        )}

        {uploadedImages.length > 0 && (
          <div style={{ padding: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap', borderTop: '1px solid #e2e8f0' }}>
            {uploadedImages.map((img, index) => (
              <div key={index} style={{ position: 'relative', width: '60px', height: '60px' }}>
                <img src={img.localUrl} alt={img.fileName} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '6px' }} />
                <button
                  onClick={() => removeUploadedImage(index)}
                  style={{
                    position: 'absolute',
                    top: '-6px',
                    right: '-6px',
                    width: '20px',
                    height: '20px',
                    minWidth: '20px',
                    minHeight: '20px',
                    padding: '0',
                    borderRadius: '50%',
                    background: '#ffffff',
                    color: '#1a1a1a',
                    border: '1px solid #9ca3af',
                    cursor: 'pointer',
                    fontSize: '14px',
                    fontWeight: 'bold',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    lineHeight: '1'
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        <div className="input-area" id="chat-input-area">
          <button className="btn-icon" onClick={handleImageButtonClick} disabled={connectionStatus !== 'connected' || isUploadingImage}>
            {isUploadingImage ? (
              <Loader2 size={20} className="spin" />
            ) : (
              <ImageIcon size={20} />
            )}
          </button>
          <input
            id="chat-input"
            className="msg-input"
            placeholder="Message..."
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={connectionStatus !== 'connected'}
          />
          <button onClick={handleSend} disabled={connectionStatus !== 'connected' || isUploadingImage || isDeletingImage || (!inputText.trim() && uploadedImages.length === 0)} className="btn-primary" id="send-btn">
            {isDeletingImage ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
          </button>
        </div>
      </div>

      {/* COLUMN 2: EDITOR (Center, Main Focus) */}
      <div className="panel editor-panel">
        {!editingKB ? (
          <>
            <div className="header">
              <h3 className="header-title"><Settings size={18} /> System Prompt</h3>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={loadConfig} disabled={isLoadingConfig} className="btn-icon">
                  <RefreshCw size={18} className={isLoadingConfig ? "spin" : ""} />
                </button>
                <button
                  onClick={saveConfig}
                  disabled={
                    !systemPrompt.trim() ||
                    isSavingConfig ||
                    !apiKey ||
                    !agentId ||
                    (systemPrompt === loadedSystemPrompt && JSON.stringify(selectedKBMap) === JSON.stringify(loadedKBMap))
                  }
                  className="btn-primary"
                >
                  <Save size={16} /> {isSavingConfig ? 'UPDATING...' : 'UPDATE AGENT SETTINGS'}
                </button>
              </div>
            </div>
            <textarea
              className="prompt-editor"
              value={systemPrompt}
              onChange={e => setSystemPrompt(e.target.value)}
              placeholder="Load config to edit system prompt..."
            />
            <div className="char-count">{systemPrompt.length} chars</div>

            <MemoryViewer
              isExpanded={memoryExpanded}
              onToggle={() => setMemoryExpanded(!memoryExpanded)}
              globalMemories={globalMemories}
              isLoading={isLoadingMemories}
              sessionId={currentSessionId}
              userId={TEST_USER_ID}
              onDeleteMemory={handleDeleteMemory}
            />
          </>
        ) : (
          <>
            <div className="header">
              <h3 className="header-title">
                <BookOpen size={18} /> Edit: {editingKB.name}
              </h3>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={() => handleDeleteKB(editingKB.id)} className="btn-red-outline">
                  <Trash2 size={16} /> Delete
                </button>
                <button onClick={() => setEditingKB(null)} className="btn-black">
                  <ArrowLeft size={16} /> Back
                </button>
              </div>
            </div>
            <div className="editor-content">
              <div className="form-group">
                <label className="form-label">Name</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <input
                    value={editingKB.name}
                    onChange={e => setEditingKB({ ...editingKB, name: e.target.value })}
                    style={{ flex: 1 }}
                  />
                  <button onClick={() => handleRenameKB(editingKB.id, editingKB.name)} className="btn-black" style={{ padding: '8px 12px' }}>
                    Rename
                  </button>
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">ID</label>
                <code style={{ background: '#f1f5f9', padding: '4px 8px', borderRadius: '4px' }}>{editingKB.id}</code>
              </div>
              <div className="form-group">
                <label className="form-label">Type</label>
                <span className="badge">{editingKB.type}</span>
              </div>
              <div className="form-group" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <label className="form-label">Content (Read-Only Preview)</label>
                <div className="content-preview">
                  {kbContent}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* COLUMN 3: CONFIG (Far Right) */}
      <div className="config-panel">

        {/* Credentials & Model */}
        <div className="card">
          <div className="form-group">
            <label className="form-label">Elevenlabs API Key</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type={showApiKey ? "text" : "password"}
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder="xi-..."
                style={{ flex: 1 }}
              />
              <button onClick={() => setShowApiKey(!showApiKey)} className="btn-icon">
                {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <label className="form-label" style={{ margin: 0 }}>Agent ID</label>
              {configAgentName && (
                <span
                  className="config-agent-name"
                  onMouseEnter={() => setIsHoveringAgentName(true)}
                  onMouseLeave={() => setIsHoveringAgentName(false)}
                  style={{
                    fontSize: '10px',
                    color: '#64748b',
                    maxWidth: isHoveringAgentName ? 'none' : '120px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    cursor: 'default',
                    transition: 'max-width 0.2s ease'
                  }}
                >
                  {isHoveringAgentName ? configAgentName : (configAgentName.length > 25 ? configAgentName.slice(0, 25) + '...' : configAgentName)}
                </span>
              )}
              {isFetchingAgentName && (
                <div className="spinner-sm"></div>
              )}
            </div>
            <input value={agentId} onChange={e => setAgentId(e.target.value)} placeholder="agent-id" />
          </div>

          <button
            className="btn-black"
            style={{ width: '100%', justifyContent: 'center', marginTop: '10px' }}
            onClick={() => {
              sessionStorage.setItem("xi-api-key", apiKey);
              sessionStorage.setItem("xi-agent-id", agentId);
              setSavedApiKey(apiKey);
              setSavedAgentId(agentId);
              alert("Credentials saved to session!");
            }}
            disabled={apiKey === savedApiKey && agentId === savedAgentId}
          >
            Set Credentials
          </button>

          <div className="separator" style={{ height: '1px', background: '#e2e8f0', margin: '15px 0' }} />

          {/* Non-functional LLM Fields */}
          <div className="form-group" style={{ opacity: 0.6 }}>
            <label className="form-label">Service (Managed by Agent)</label>
            <select disabled style={{ width: '100%', padding: '8px', borderRadius: '6px', background: '#f8fafc', border: '1px solid #e2e8f0' }}>
              <option>Default Provider</option>
            </select>
          </div>
          <div className="form-group" style={{ opacity: 0.6 }}>
            <label className="form-label">Model ID (Managed by Agent)</label>
            <input disabled placeholder="Managed by Agent Settings" style={{ width: '100%', padding: '8px', borderRadius: '6px', background: '#f8fafc', border: '1px solid #e2e8f0' }} />
          </div>

        </div>

        {/* KB List */}
        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div className="header-small" style={{ marginBottom: '10px' }}>
            <h3 className="header-title" style={{ fontSize: '0.85rem' }}>
              <BookOpen size={16} />
              Knowledge Base
            </h3>
            <span className="badge">{Object.keys(selectedKBMap).length} Active</span>
          </div>

          <div className="kb-list-container">
            {availableKBs.length === 0 && (
              <div style={{ padding: '10px', color: '#94a3b8', fontStyle: 'italic', fontSize: '13px' }}>
                {isLoadingConfig ? "Loading..." : "No KBs found."}
              </div>
            )}
            {availableKBs.map(kb => {
              const isSelected = !!selectedKBMap[kb.id];
              return (
                <div key={kb.id} className={`kb-item ${isSelected ? 'selected' : ''}`}
                  onClick={() => toggleKB(kb)}>
                  {isSelected ? <CheckSquare size={16} className="text-blue-500" /> : <Square size={16} color="#cbd5e1" />}
                  <div className="kb-info">
                    <div className="kb-name">{kb.name}</div>
                    <div className="kb-type">{kb.type}</div>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); handleEditKB(kb); }} className="btn-icon-sm">
                    <Edit2 size={12} />
                  </button>
                </div>
              )
            })}
          </div>
        </div>

      </div>


    </div >
  )
}

export default App;
