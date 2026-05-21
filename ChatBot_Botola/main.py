# chatbot-service/main.py
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from src.chat_orchestrator import ChatOrchestrator
from src.logger import get_logger

logger = get_logger("botola.main")

# ---------------------------------------------------------------------------
# Application lifespan (replaces deprecated @app.on_event)
# ---------------------------------------------------------------------------

orchestrator: Optional[ChatOrchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup → yield → Shutdown."""
    global orchestrator
    logger.info("Starting Botola Pro Chatbot v4...")
    orchestrator = ChatOrchestrator()
    logger.info("Server is ready")
    yield
    if orchestrator:
        await orchestrator.close()
    logger.info("Server shut down cleanly")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Botola Pro Chatbot",
    version="4.0.0",
    description="Production-ready AI chatbot with Hybrid RAG, Dynamic DB, LLM, and Action Routing",
    lifespan=lifespan,
)

# CORS — restrict to known origins in production
_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=r"null|file://.*",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
)


# (lifecycle is handled by lifespan context manager above)


# ============== MODELS ==============

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str
    language: str = "auto"


class ChatResponse(BaseModel):
    type: str
    message: str
    data: Dict = {}
    actions: List[Dict] = []
    sources: List[str] = []
    metadata: Dict = {}


# ============== REST ENDPOINTS ==============

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not orchestrator:
        raise HTTPException(503, "Chatbot not initialized")
    
    result = await orchestrator.process(
        user_id=req.user_id,
        session_id=req.session_id,
        message=req.message,
        language=req.language
    )
    return ChatResponse(**result)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "4.0.0",
        "components": {
            "rag": orchestrator.rag.is_ready if orchestrator else False,
            "llm": orchestrator.llm.provider if orchestrator else None,
            "memory": "redis" if orchestrator and orchestrator.memory.redis else "in-memory",
        },
    }


@app.get("/api/debug/intent")
async def debug_intent(message: str):
    if not orchestrator:
        raise HTTPException(503, "Not initialized")
    return orchestrator.classifier.classify(message)


@app.get("/api/debug/history/{session_id}")
async def debug_history(session_id: str):
    if not orchestrator:
        raise HTTPException(503, "Not initialized")
    return {
        "session_id": session_id,
        "history": orchestrator.memory.get_history(session_id),
    }


# ============== STREAMING ENDPOINT ==============

@app.post("/api/chat/stream")
async def chat_stream(req: "ChatRequest"):
    """Server-Sent Events endpoint for real-time token streaming."""
    if not orchestrator:
        raise HTTPException(503, "Chatbot not initialized")

    history_turns = orchestrator.memory.get_history(req.session_id)
    classification = orchestrator.classifier.classify(req.message)
    context_str = ""

    if classification["route"] == "static":
        contextual_query = orchestrator._rewrite_query(req.message, history_turns)
        rag_result = orchestrator.rag.answer(contextual_query)
        context_str = f"STADIUM DOCUMENTS:\n{rag_result['context']}" if rag_result["has_context"] else ""

    llm_history = orchestrator._history_to_messages(history_turns)

    async def event_generator() -> AsyncGenerator[str, None]:
        full_text = ""
        async for token in orchestrator.llm.stream(
            query=req.message,
            context=context_str,
            history=llm_history,
            language=req.language,
        ):
            full_text += token
            yield f"data: {json.dumps({'token': token})}\n\n"

        # Save complete response to memory
        orchestrator.memory.add_turn(req.session_id, "user", req.message, {})
        orchestrator.memory.add_turn(req.session_id, "assistant", full_text, {})
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ============== WEBSOCKET (Real-time Chat) ==============

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
    
    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
    
    async def send_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    # Validate that client_id is a valid UUID to prevent path injection
    try:
        uuid.UUID(client_id)
    except ValueError:
        await websocket.close(code=1008, reason="Invalid client_id format")
        return

    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            result = await orchestrator.process(
                user_id=payload.get("user_id", client_id),
                session_id=payload.get("session_id", client_id),
                message=payload.get("message", ""),
                language=payload.get("language", "auto"),
            )

            await manager.send_message(json.dumps(result), client_id)

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        logger.info("WebSocket disconnected", extra={"client_id": client_id})


# ============== STANDALONE TEST UI ==============

@app.get("/chatbot-test", response_class=HTMLResponse)
async def chatbot_test():
    """
    Standalone HTML test interface for the chatbot.
    Use this when frontend teammate is not available.
    """
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Botola Pro AI - Premium</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        :root {
            --dark-blue: #0A192F;
            --mid-blue: #1E3A8A;
            --accent-blue: #2563EB;
            --light-blue: #EFF6FF;
            --white: #FFFFFF;
            --off-white: #F8FAFC;
            --text-dark: #0F172A;
            --text-muted: #64748B;
            --text-light: #F8FAFC;
            --border-light: #E2E8F0;
            --border-dark: rgba(255,255,255,0.1);
            --shadow-sm: 0 1px 3px rgba(10, 25, 47, 0.05);
            --shadow-md: 0 4px 12px rgba(10, 25, 47, 0.08);
            --shadow-lg: 0 12px 24px rgba(10, 25, 47, 0.12);
        }

        body.dark-mode {
            --white: #0A192F;
            --off-white: #050B14;
            --text-dark: #F8FAFC;
            --text-muted: #94A3B8;
            --border-light: #1E293B;
            --light-blue: #1E293B;
            --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.2);
            --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.3);
            --shadow-lg: 0 12px 24px rgba(0, 0, 0, 0.4);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Outfit', -apple-system, sans-serif;
            background: var(--off-white);
            color: var(--text-dark);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .header {
            background: var(--white);
            padding: 16px 32px;
            border-bottom: 1px solid var(--border-light);
            display: flex;
            align-items: center;
            gap: 16px;
            z-index: 10;
            box-shadow: var(--shadow-sm);
        }

        .header-icon {
            width: 40px; height: 40px;
            background: var(--accent-blue);
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
        }

        .header-title {
            font-size: 18px; font-weight: 700; color: var(--dark-blue); letter-spacing: -0.3px;
        }

        .header-sub {
            font-size: 13px; color: var(--text-muted); font-weight: 400;
        }

        .status {
            margin-left: auto;
            display: flex; align-items: center; gap: 8px;
            font-size: 13px; color: #059669; font-weight: 600;
            background: #D1FAE5;
            padding: 6px 14px;
            border-radius: 20px;
            border: 1px solid #34D399;
        }

        .status-dot {
            width: 8px; height: 8px;
            background: #10B981;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.1); }
        }

        .main {
            flex: 1;
            display: flex;
            overflow: hidden;
            position: relative;
        }

        .sidebar {
            width: 320px;
            background: var(--dark-blue);
            color: var(--text-light);
            padding: 32px 24px;
            overflow-y: auto;
            z-index: 5;
            box-shadow: inset -1px 0 0 rgba(0,0,0,0.2);
        }

        .sidebar h3 {
            font-size: 12px; text-transform: uppercase;
            letter-spacing: 1.2px; color: #94A3B8;
            margin-bottom: 20px; font-weight: 600;
        }

        .test-case {
            background: rgba(255,255,255,0.04);
            border: 1px solid var(--border-dark);
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 12px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            color: var(--text-light);
            transition: all 0.2s ease;
            position: relative;
        }

        .test-case:hover {
            background: rgba(255,255,255,0.08);
            border-color: rgba(255,255,255,0.2);
            transform: translateX(4px);
        }

        .test-case .tag {
            display: inline-block;
            font-size: 10px; font-weight: 700; padding: 4px 8px;
            border-radius: 6px; margin-top: 10px; letter-spacing: 0.5px;
        }

        .tag-static { background: rgba(59, 130, 246, 0.2); color: #93C5FD; }
        .tag-dynamic { background: rgba(16, 185, 129, 0.2); color: #6EE7B7; }
        .tag-fallback { background: rgba(245, 158, 11, 0.2); color: #FCD34D; }

        .chat-area {
            flex: 1; display: flex; flex-direction: column;
            background: var(--off-white);
            position: relative;
        }

        .messages {
            flex: 1; overflow-y: auto; display: flex; flex-direction: column;
            gap: 24px; padding: 40px; scroll-behavior: smooth;
        }

        .message {
            max-width: 75%; padding: 18px 24px; border-radius: 16px;
            font-size: 15px; line-height: 1.6;
            animation: slideUp 0.3s ease-out;
            box-shadow: var(--shadow-sm);
        }

        @keyframes slideUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            align-self: flex-end; background: var(--accent-blue);
            color: var(--white); border-bottom-right-radius: 4px;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
        }

        .message.bot {
            align-self: flex-start; background: var(--white);
            color: var(--text-dark); border: 1px solid var(--border-light);
            border-bottom-left-radius: 4px;
        }

        .message.bot strong { color: var(--dark-blue); font-weight: 700; }

        .message.bot .meta {
            font-size: 11px; color: var(--text-muted);
            margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--border-light);
            display: flex; gap: 12px; font-weight: 500;
        }

        .message.bot .actions {
            display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap;
        }

        .action-btn {
            background: var(--white); border: 1px solid var(--border-light);
            color: var(--dark-blue); padding: 8px 16px; border-radius: 8px;
            font-size: 13px; font-weight: 600; cursor: pointer;
            transition: all 0.2s; font-family: 'Outfit', sans-serif;
            box-shadow: var(--shadow-sm);
        }

        .action-btn:hover {
            background: var(--light-blue); border-color: var(--accent-blue);
            color: var(--accent-blue); transform: translateY(-1px);
        }

        .input-area {
            display: flex; gap: 16px; padding: 24px 40px 32px;
            background: linear-gradient(to top, var(--off-white) 80%, transparent);
            position: relative; z-index: 10;
        }

        .input-area input {
            flex: 1; background: var(--white);
            border: 1px solid var(--border-light); color: var(--text-dark);
            padding: 18px 24px; border-radius: 16px; font-size: 15px;
            outline: none; transition: all 0.2s;
            font-family: 'Outfit', sans-serif;
            box-shadow: var(--shadow-md);
        }

        .input-area input::placeholder { color: var(--text-muted); }

        .input-area input:focus {
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
        }

        .input-area button {
            background: var(--accent-blue); color: var(--white); border: none;
            padding: 0 32px; border-radius: 16px; font-size: 15px;
            font-weight: 600; cursor: pointer; transition: all 0.2s;
            font-family: 'Outfit', sans-serif;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
            display: flex; align-items: center; justify-content: center; gap: 8px;
        }

        .input-area button:hover {
            background: #1D4ED8; transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(37, 99, 235, 0.3);
        }

        .input-area button:disabled {
            opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none;
        }

        .typing {
            display: none; align-self: flex-start; background: var(--white);
            border: 1px solid var(--border-light); padding: 18px 24px;
            border-radius: 16px; border-bottom-left-radius: 4px;
            margin-left: 40px; margin-bottom: 20px; box-shadow: var(--shadow-sm);
        }

        .typing.visible { display: flex; align-items: center; }

        .dots { display: flex; gap: 6px; }

        .dots span {
            width: 8px; height: 8px; background: var(--accent-blue); border-radius: 50%;
            animation: bounce 1.4s infinite ease-in-out both;
        }

        .dots span:nth-child(1) { animation-delay: -0.32s; }
        .dots span:nth-child(2) { animation-delay: -0.16s; }

        .debug-panel {
            position: fixed; bottom: 100px; right: 40px;
            background: var(--dark-blue); color: var(--white);
            border: 1px solid var(--border-dark); border-radius: 16px;
            padding: 24px; width: 400px; max-height: 500px; overflow-y: auto;
            font-size: 13px; display: none; z-index: 50;
            box-shadow: var(--shadow-lg);
        }

        .debug-panel.visible { display: block; animation: slideUp 0.3s ease; }
        
        .debug-panel pre { color: #6EE7B7; font-family: monospace; white-space: pre-wrap; }

        .header-actions {
            display: flex; gap: 12px; margin-left: auto; align-items: center;
        }

        .icon-btn {
            background: transparent; border: 1px solid var(--border-light);
            color: var(--text-muted); width: 36px; height: 36px;
            border-radius: 8px; cursor: pointer; display: flex;
            align-items: center; justify-content: center; transition: all 0.2s;
        }

        .icon-btn:hover {
            background: var(--light-blue); color: var(--accent-blue);
            border-color: var(--accent-blue);
        }
        
        .feature-list { list-style: none; margin: 20px 0; padding: 0; }
        .feature-list li { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; font-weight: 400; }
        .feature-list li i { color: var(--accent-blue); }
        .welcome-header { display: flex; align-items: center; gap: 10px; font-weight: 600; margin-bottom: 12px; font-size: 16px; color: var(--dark-blue); }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-icon"><i data-lucide="bot" style="color: white; width: 24px; height: 24px;"></i></div>
        <div>
            <div class="header-title">Botola Pro AI</div>
            <div class="header-sub">Static RAG + Dynamic DB + Mistral LLM</div>
        </div>
        <div class="status" style="margin-left: 20px;">
            <div class="status-dot"></div>
            <span>Online</span>
        </div>
        <div class="header-actions">
            <button class="icon-btn" onclick="toggleTheme()" title="Toggle Dark Mode">
                <i data-lucide="moon" id="theme-icon"></i>
            </button>
            <button class="icon-btn" onclick="toggleDebug()" title="Toggle Debug Panel">
                <i data-lucide="terminal"></i>
            </button>
        </div>
    </div>
    
    <div class="main">
        <div class="sidebar">
            <h3>Test Cases</h3>
            <div class="test-case" onclick="sendTest('Can I bring a backpack to the stadium?')">
                Can I bring a backpack?
                <span class="tag tag-static">STATIC</span>
            </div>
            <div class="test-case" onclick="sendTest('Where is my seat for Raja vs MAS?')">
                Where is my seat?
                <span class="tag tag-dynamic">DYNAMIC</span>
            </div>
            <div class="test-case" onclick="sendTest('Show my tickets')">
                Show my tickets
                <span class="tag tag-dynamic">DYNAMIC</span>
            </div>
            <div class="test-case" onclick="sendTest('What time does WAC vs FAR start?')">
                Match time?
                <span class="tag tag-dynamic">DYNAMIC</span>
            </div>
            <div class="test-case" onclick="sendTest('How much is a VIP ticket?')">
                VIP price?
                <span class="tag tag-dynamic">DYNAMIC</span>
            </div>
            <div class="test-case" onclick="sendTest('What are the betting odds?')">
                Betting odds (BLOCKED)
                <span class="tag tag-fallback">GUARDRAIL</span>
            </div>
            <div class="test-case" onclick="sendTest('متى تفتح بوابات الملعب؟')">
                Arabic: Gate time?
                <span class="tag tag-static">STATIC</span>
            </div>
            <div class="test-case" onclick="sendTest('Transfer my ticket to Karim')">
                Transfer ticket
                <span class="tag tag-dynamic">DYNAMIC</span>
            </div>
            
            <h3 style="margin-top: 24px;">Session</h3>
            <div style="font-size: 12px; color: #64748b;">
                ID: <span id="session-id">loading...</span><br>
                User: u_buyer_001
            </div>
        </div>
        
        <div class="chat-area">
            <div class="messages" id="messages">
                <div class="message bot">
                    <div class="welcome-header">
                        <i data-lucide="message-circle" style="width:16px;height:16px;color:#38bdf8;"></i> Ahlan! I'm Botola Pro AI. I can help you with:
                    </div>
                    <ul class="feature-list">
                        <li><i data-lucide="ticket" style="width:16px;height:16px;"></i> Ticket info, seats, and match times</li>
                        <li><i data-lucide="map-pin" style="width:16px;height:16px;"></i> Stadium rules and policies</li>
                        <li><i data-lucide="shield-check" style="width:16px;height:16px;"></i> Security and verification</li>
                        <li><i data-lucide="credit-card" style="width:16px;height:16px;"></i> Pricing and availability</li>
                    </ul>
                    Try the test cases on the left, or type your own question!
                </div>
            </div>
            <div class="typing" id="typing">
                <div class="dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
            <div class="input-area">
                <input type="text" id="message-input" 
                       placeholder="Ask about tickets, stadium rules, or matches..."
                       onkeypress="if(event.key==='Enter') sendMessage()">
                <button onclick="sendMessage()" id="send-btn">Send</button>
            </div>
        </div>
    </div>
    
    <!-- Debug toggle moved to header -->
    <div class="debug-panel" id="debug-panel">
        <h3 style="margin-bottom: 10px;">Debug Info</h3>
        <div id="debug-content">No data yet...</div>
    </div>

    <script>
        const SESSION_ID = 'test_' + Math.random().toString(36).substr(2, 9);
        document.getElementById('session-id').textContent = SESSION_ID;
        
        const API_URL = window.location.origin + '/api/chat';
        
        function addMessage(text, isUser = false, metadata = null, actions = []) {
            const container = document.getElementById('messages');
            const msg = document.createElement('div');
            msg.className = `message ${isUser ? 'user' : 'bot'}`;
            
            let html = text.replace(/\\n/g, '<br>');
            
            if (!isUser && metadata) {
                html += `<div class="meta">
                    Intent: <strong>${metadata.intent}</strong> (${metadata.route}) | 
                    Confidence: ${metadata.confidence} | 
                    Time: ${metadata.processing_time_ms}ms
                </div>`;
            }
            
            if (!isUser && actions.length > 0) {
                html += `<div class="actions">
                    ${actions.map(a => `<button class="action-btn" onclick="alert('Action: ${a.action}')">${a.label}</button>`).join('')}
                </div>`;
            }
            
            msg.innerHTML = html;
            container.appendChild(msg);
            container.scrollTop = container.scrollHeight;
            lucide.createIcons();
        }
        
        function setTyping(show) {
            document.getElementById('typing').classList.toggle('visible', show);
        }
        
        function setLoading(loading) {
            document.getElementById('send-btn').disabled = loading;
        }
        
        async function sendMessage() {
            const input = document.getElementById('message-input');
            const text = input.value.trim();
            if (!text) return;
            
            addMessage(text, true);
            input.value = '';
            setTyping(true);
            setLoading(true);
            
            try {
                const res = await fetch(API_URL, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_id: 'u_buyer_001',
                        session_id: SESSION_ID,
                        message: text,
                        language: 'auto'
                    })
                });
                
                const data = await res.json();
                setTyping(false);
                setLoading(false);
                
                addMessage(data.message, false, data.metadata, data.actions);
                
                // Update debug panel
                document.getElementById('debug-content').innerHTML = 
                    '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
                
            } catch (err) {
                setTyping(false);
                setLoading(false);
                addMessage('❌ Error: ' + err.message, false);
            }
        }
        
        function sendTest(text) {
            document.getElementById('message-input').value = text;
            sendMessage();
        }
        
        function toggleDebug() {
            document.getElementById('debug-panel').classList.toggle('visible');
        }

        function toggleTheme() {
            document.body.classList.toggle('dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            
            const iconEl = document.getElementById('theme-icon');
            if (iconEl) {
                iconEl.setAttribute('data-lucide', isDark ? 'sun' : 'moon');
                lucide.createIcons();
            }
        }

        if (localStorage.getItem('theme') === 'dark') {
            document.body.classList.add('dark-mode');
            const iconEl = document.getElementById('theme-icon');
            if (iconEl) iconEl.setAttribute('data-lucide', 'sun');
        }
        
        lucide.createIcons();
    </script>
</body>
</html>
    """


# ============== SAMPLE DOCUMENTS ==============

def _create_sample_documents():
    from src.config import RAW_DIR
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    samples = {
        "stade_mohammed_v_rules.txt": """STADE MOHAMMED V — FAN GUIDE
        
GATE OPENING TIMES:
- Gates open 2 hours before kick-off
- VIP entrance opens 2.5 hours before kick-off
- Last entry is 15 minutes after kick-off

BAG POLICY:
- Small bags (max 30x30x15cm) are permitted after security check
- Large backpacks, suitcases, and duffel bags are PROHIBITED
- Clear bags are recommended for faster entry

PROHIBITED ITEMS:
- Weapons, fireworks, flares
- Professional cameras with detachable lenses
- Drones and remote-controlled devices
- Alcohol and glass bottles
- Political banners and offensive materials

FOOD & DRINK:
- Sealed plastic water bottles up to 500ml are allowed
- Small snacks in sealed packaging permitted
- No outside hot food or beverages

ACCESSIBILITY:
- Wheelchair-accessible entrances at Gates A and D
- Companion seating available with prior registration
- Elevators to all levels

PARKING:
- Limited parking available (2,000 spaces)
- Arrive early or use public transport
- Tramway T1 stops 5 minutes walk from Gate B
""",
        "faq_general.txt": """BOTOLA PRO — FREQUENTLY ASKED QUESTIONS

Q: Can I transfer my ticket to someone else?
A: Yes, through the Botola Pro app. The recipient must have a verified account. A new dynamic QR code will be generated.

Q: What happens if it rains?
A: Matches proceed in light rain. Only severe weather (lightning, flooding) causes delays. Check the app for updates.

Q: Is there parking at the stadium?
A: Limited parking is available. We strongly recommend public transport (Tramway T1, bus lines 15, 23, 45).

Q: Can I bring my child?
A: Children under 6 enter free with a ticket-holding adult. Family zones are available in Tribune Sud.

Q: What is dynamic QR?
A: Your ticket QR code refreshes every 30 seconds with a new cryptographic hash. Screenshots will not work at the gate.

Q: What if I lose my phone?
A: Visit the ticket office with your ID. They can print a paper backup with a static QR valid for one scan.

Q: Can I get a refund?
A: Refunds are available up to 48 hours before the match through the app. After that, tickets are non-refundable but can be resold on the marketplace.
""",
        "bag_policy_detailed.txt": """DETAILED BAG AND SECURITY POLICY

PERMITTED ITEMS:
✓ Small purses and clutch bags (max 20x15x5cm)
✓ Clear plastic bags (max 30x30x15cm)
✓ Small backpacks for medical supplies (with medical certificate)
✓ Baby bags (with infant present)
✓ Flags and banners without poles (max 1x1.5m)

PROHIBITED ITEMS:
✗ Large backpacks and rucksacks
✗ Suitcases, duffel bags, roller bags
✗ Laptop bags and briefcases
✗ Camera bags with multiple lenses
✗ Coolers and insulated bags

SECURITY CHECKPOINT:
All bags are subject to X-ray screening. Prohibited items will be confiscated or you will be denied entry. No storage facilities are available at the stadium.

RECOMMENDATION:
Travel light. Bring only essentials: phone, wallet, keys, small bag. This ensures fastest entry through security.
"""
    }
    
    for filename, content in samples.items():
        path = RAW_DIR / filename
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)