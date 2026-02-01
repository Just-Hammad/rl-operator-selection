# ArtSensei Testing App

Admin and testing interface for Marcel — the ArtSensei ElevenLabs conversational AI art tutor.

**Live:** https://art-sensei-testing.vercel.app/

## What It Does

Three-panel layout for testing and configuring Marcel agent variants:

- **Left — Chat:** Real-time conversation with Marcel via ElevenLabs WebSocket. Supports image upload, drag-drop, and a vision "point to object" feature that highlights areas in uploaded artwork.
- **Center — Editor:** System prompt editor with load/save to ElevenLabs API, plus a memory viewer showing session and global memories.
- **Right — Config:** API key/agent ID inputs, knowledge base list with checkboxes to select which KBs the agent uses.

## Integrations

- **ElevenLabs Conversational AI API** — connects via signed WebSocket URL, manages agent config via REST
- **Backend on Railway** (`mvp-backend-production-4c8b.up.railway.app`) — handles signed URLs, memory CRUD, image upload, vision/pointing
- **Supabase** — session persistence (`chat_sessions` table)

## Memory System

Dual-layer memory injected into prompts via template variables:

- `{{session_context}}` — short-term session memories (current conversation)
- `{{global_context}}` — long-term user knowledge (persistent across sessions)

Both layers poll the backend every 8 seconds and are formatted into the system prompt at runtime.

## Agent Variants

12 agent configurations in `src/constants.js` for testing different setups (MVP, text-only, KB & RAG, beta, draw-specific, etc.).

## Knowledge Base

`marcel-artwork-library.md` (4,734 lines) — comprehensive reference covering drawing marks, painting techniques, and universal concepts (composition, color, shape) with detailed artist analyses. Formatted for upload as an ElevenLabs KB document.

## Project Structure

```
src/
├── App.jsx              — Main app component (three-panel layout)
├── App.css              — Styling
├── constants.js         — Agent ID list
├── utils.js             — Memory formatting utilities
├── components/
│   ├── Dialogue.jsx     — Modal for prompt variable examples
│   └── MemoryViewer.jsx — Memory display with delete controls
├── services/
│   ├── memoryService.js — Memory API calls
│   └── sessionManager.js — Session creation/storage via Supabase
├── lib/
│   ├── supabaseClient.js
│   └── supabaseConfig.js
└── utils/
    ├── route.js         — Backend URL config
    └── memoryUtils.js   — Memory layer utilities
```

## Environment Variables

```
VITE_ELEVENLABS_API_KEY  — ElevenLabs API key (can also be set in UI)
VITE_AGENT_ID            — Default agent ID (can also be set in UI)
VITE_SUPABASE_URL        — Supabase project URL
VITE_SUPABASE_ANON_KEY   — Supabase anonymous key
```

## Dev Setup

```bash
npm install
npm run dev
```

## Tech Stack

- React 19 + Vite 7
- @elevenlabs/react (v0.12.1)
- @supabase/supabase-js (v2.87.0)
- Axios, Lucide React icons, Tailwind CSS v4
