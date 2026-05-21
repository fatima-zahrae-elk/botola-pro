---
title: Botola Pro Chatbot API
emoji: ⚽
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Botola Pro — Ticketing Platform

Smart · Secure · Fair — AI-powered ticket platform for Botola Pro.

---

## What's inside

| Folder / File | Description |
|---|---|
| `dashboard.html` | Project management dashboard (Gantt, tasks, models, team) |
| `Prototype/` | Full platform prototype (Buyer · Seller · Admin) |
| `ChatBot_Botola/` | ChatBot FastAPI backend (RAG + Mistral LLM) |
| `ChatBot_Botola/models_cache/` | Pre-bundled AI models — **no internet needed** |
| `setup.bat` | One-time setup — creates venv and installs packages |
| `start.bat` | Launches everything with one double-click |

---

## Requirements

- **Python 3.10** — download from https://www.python.org/downloads/release/python-3100/
  - During install: check **"Add Python to PATH"**
- **Internet** — only needed during `setup.bat` to install Python packages (~150 MB)
- Windows 10 or 11

---

## First-time setup (run once)

1. Unzip the folder anywhere on your laptop
2. Double-click **`setup.bat`**
3. Wait for it to finish (2–5 minutes depending on your connection)
4. You should see: `Setup complete! Run START.BAT to launch everything.`

---

## Every time you want to run it

Double-click **`start.bat`**

That's it. Two terminal windows will open and your browser will launch automatically.

---

## Links (after start.bat)

| | URL |
|---|---|
| Project Dashboard | http://localhost:5500/dashboard.html |
| Platform Prototype | http://localhost:5500/Prototype/prototype%20copy.html |
| ChatBot Test UI | http://localhost:8000/chatbot-test |

> Wait ~30 seconds after start.bat for the ChatBot window to show  
> `Application startup complete` before using the chatbot.

---

## Stopping the servers

Close the two terminal windows titled **Dashboard-Server** and **ChatBot-Server**.

---

## Troubleshooting

**"Python not found" during setup**  
→ Re-install Python 3.10 and check "Add Python to PATH"

**"venv not found" when starting**  
→ Run `setup.bat` first

**ChatBot shows "Could not reach API"**  
→ Wait 30 more seconds — the AI model is still loading  
→ Check that the ChatBot-Server window is open and shows `Application startup complete`

**Port already in use**  
→ `start.bat` clears ports 5500 and 8000 automatically on each launch

---

## API key

The chatbot uses the Mistral API. The key is already set in `ChatBot_Botola/.env`.  
No action needed.
