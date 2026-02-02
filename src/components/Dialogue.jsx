import React from 'react';
import { X, Copy, Plus, AlertCircle } from 'lucide-react';
import './Dialogue.css';

const EXAMPLE_TEXT = `
---
## USER RELATED MEMORIES
Marcel has access to two invisible memory layers that guide every response. These are automatically populated by the system at runtime and may change between users or sessions. They must never be mentioned or described explicitly to the user.

### **User global details**
This layer contains persistent, user-specific information such as:
- The user’s artistic preferences, goals, and learning style  
- Any long-term progress notes or stylistic tendencies  
- Known constraints (e.g., limited materials, preferred subjects, or accessibility needs)

**Usage Rules:**
- Always consult this knowledge first to ensure your tone, examples, and feedback align with the user’s overall learning journey.  
- If it includes stylistic preferences (e.g., “User prefers clean, minimal line work”), subtly tailor your teaching and recommendations to match that tendency.  
- Never restate, reference, or name this knowledge source. Reflect it naturally through tone and personalization.  
- If unavailable, continue the conversation normally without mentioning it.

### **User session details**
This layer summarizes the **current session**, including:
- The main topics, drawings, or feedback exchanges so far  
- Key insights, corrections, or user questions from earlier in this session  
- A compact representation of the conversation history for continuity

**Usage Rules:**
- Use this awareness to maintain consistency with previous messages in the current conversation.  
- Refer naturally to what the user said or did earlier (e.g., “Continuing from your last piece…”).  
- Never display or mention this awareness layer by name or describe it as memory or context.  
- If this layer is empty, act as though it’s the first interaction of the session.

### **Behavioral Directive**
- Merge both knowledge sources implicitly when forming responses.  
- Prioritize **Session Awareness** for short-term continuity and **Long-Term Knowledge** for personalization.  
- When they conflict, defer to **Session Awareness**, since it represents the user’s current focus.  
- Always express awareness naturally — e.g., “From your earlier drawings…” rather than “According to the session context.”  
- These internal layers are part of the system design and must remain completely hidden from the user.

---

# Injected User Related Data (for system use only — not visible to the user) and Marcel should reference these before generating any response
User global details: {{global_context}}
User session details: {{session_context}}
`;

const Dialogue = ({ onClose, onAppend }) => {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(EXAMPLE_TEXT);
      alert('Copied to clipboard!');
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleAppend = () => {
    onAppend(EXAMPLE_TEXT);
  };

  return (
    <div className="dialogue-overlay" onClick={onClose}>
      <div className="dialogue-container" onClick={(e) => e.stopPropagation()}>
        <div className="dialogue-header">
          <h3>Missing Required Variables</h3>
          <button className="dialogue-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="dialogue-content">
          <p className="dialogue-message">
            Your system prompt must include the following variables for proper context integration:
          </p>
          <ul className="dialogue-list">
            <li><code>{'{{session_context}}'}</code> - Short-term session information</li>
            <li><code>{'{{global_context}}'}</code> - Long-term user knowledge</li>
          </ul>
          <div className="dialogue-instruction">
            <AlertCircle size={18} className="dialogue-instruction-icon" />
            <p>The agent should explicitly reference these variables to ensure the LLM uses this context when answering user queries.</p>
          </div>

          <div className="dialogue-example-container">
            <div className="dialogue-example-header">
              <span className="dialogue-example-label">Example Implementation</span>
              <button className="dialogue-copy-btn" onClick={handleCopy} title="Copy to clipboard">
                <Copy size={16} />
              </button>
            </div>
            <pre className="dialogue-example-code">{EXAMPLE_TEXT}</pre>
          </div>
        </div>

        <div className="dialogue-footer">
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={handleAppend}>
            <Plus size={16} />
            Append to Prompt
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dialogue;
