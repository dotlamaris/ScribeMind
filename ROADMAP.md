# Project Roadmap — June 28, 2026

## Where We Are Now

The core stack is working:
- **Flask server** (`server.py`) — serves the voice app and a logs viewer
- **Presence module** (`presence_module.py`) — processes speech transcripts, flags keywords, calls the nanobot
- **Nanobot** (`.nanobot/config.json`) — Claude Opus 4.5 agent with web search, shell exec, and file I/O; runs on websocket port 8000
- **Groq client** — handles LLM calls and transcription (Whisper via Groq)

The voice pipeline works: speak → transcribe → flag → optionally dispatch to nanobot.  
What's missing: mobile access, a reliable audio layer, Google Drive sync, and confidence that nanobot tasks actually complete.

---

## Priority 1 — Test the Nanobot (Do This First)

Before building more on top of it, understand what it can actually do reliably.

**Tests to run:**
- [ ] Shell command: `run_agent("Run 'ls -la' and return the output")`
- [ ] File write: `run_agent("Write 'hello world' to /tmp/test.txt and confirm it was written")`
- [ ] Web search: `run_agent("Search the web for today's top news and summarize 3 headlines")`
- [ ] Long task: `run_agent("Research Python asyncio timeouts and write a 200-word summary to /tmp/summary.txt")`
- [ ] Timeout behavior: what happens when a task takes > 60 seconds?

**Key question:** Does `run_agent()` block until done, or does it silently timeout and return empty?  
Current concern from session: responses may not come back reliably on complex tasks.

**Fix if needed:** Add a timeout wrapper and a result-check in `nanobot_template.py`.

---

## Priority 2 — Audio System (Server Side)

The current voice app is a web page. The audio pipeline needs to be solid before going mobile.

- [ ] Confirm the full loop works end-to-end: mic → `/api/transcribe` → presence module → flagged response returned to client
- [ ] Add a `/api/nanobot` endpoint that accepts a task string, dispatches to nanobot async, and returns a job ID
- [ ] Add a `/api/nanobot/<job_id>` polling endpoint so the client can check if the nanobot finished
  - This solves the "never got a response" problem — fire and poll, don't block
- [ ] Log all nanobot dispatches and results to the existing `ExecutionLogger`

---

## Priority 3 — Google Drive Integration

Store transcripts and nanobot outputs to Drive so nothing is lost between sessions.

- [ ] Create `services/google_drive.py` — isolated module for Drive auth and file operations
- [ ] Use a service account or OAuth2 refresh token (store credentials as environment secrets, never in code)
- [ ] Two operations to start with:
  - **Append transcript** — after each session segment, append text to a running Google Doc or `.txt` file in Drive
  - **Save nanobot output** — when a nanobot task finishes, save the result file to Drive
- [ ] Cache Drive calls aggressively (don't hit the API on every transcript segment)

---

## Priority 4 — Mobile App

The Flask server already exists — the mobile app is a client, not a rebuild.

**Option A — Progressive Web App (PWA)** — fastest path
- Modify `templates/static_recorder.html` to be mobile-responsive and installable as a PWA
- Add a Web App Manifest and service worker
- Works on iOS and Android from the browser, no app store needed
- Uses the phone's mic via the existing `getUserMedia()` web API

**Option B — React Native / Expo app** — more powerful, more work
- Separate app that hits the same Flask API endpoints
- Needed if you want background audio recording or native push notifications

**Recommendation: Start with Option A (PWA).** It shares 100% of the existing server code and gets you on mobile in hours, not weeks. Upgrade to Option B when you hit a wall the browser can't handle.

---

## Priority 5 — Server Hardening

Small things that will bite you without these in place.

- [ ] Move all secrets (Groq API key, Drive credentials) to environment variables — none in code or config files
- [ ] Add a health check endpoint `GET /health` → `{"status": "ok"}`
- [ ] Add request timeouts on all nanobot calls (suggested: 90s hard limit)
- [ ] Rate-limit the `/api/transcribe` endpoint to prevent runaway Groq usage
- [ ] Persist transcript history to a file (right now it's in-memory and resets on server restart)

---

## Sequence

```
Week 1:  Priority 1 — Nanobot testing + fix response reliability
Week 1:  Priority 2 — Async nanobot API endpoint (fire + poll)
Week 2:  Priority 3 — Google Drive service module
Week 2:  Priority 4 — PWA mobile layer
Week 3:  Priority 5 — Server hardening + secrets cleanup
```

---

## Open Questions

1. **Nanobot model** — config shows `nemotron-3-nano:30b-cloud` via a custom provider. Is this provider actually connected and working? The nanobot config also references Claude Opus 4.5 as a fallback. Which one is actually responding?
2. **Drive auth** — service account (server-to-server, no user interaction) or OAuth2 (user must authorize once)? Service account is simpler for a personal project.
3. **Mobile audio** — does the current web recorder work on mobile browsers today, or does it fail? This determines how urgent Option B is.
