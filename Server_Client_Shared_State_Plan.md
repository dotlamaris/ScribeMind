# Server Client Shared State Plan

## Goal
Modify the static recorder HTML client and its backend so that pressing **Copy All** sends the full clipboard content—including labeled question‑answer segments from past session transcripts—to the server. The server must store this data in the same format the client uses, enabling later retrieval and display.

## Scope
- **Client:** `templates/static_recorder.html` – locate the “Copy All” button handler.
- **Server:** Either `server.py` or `menu.py` (whichever defines the API endpoint for persisting clipboard data).
- **Source of Truth:** Server will store the entire transcript history in memory (or to a file) and serve it via a dedicated endpoint. The client will fetch this data instead of sending clipboard content on copy.

## Steps

### 1. Client-side Changes
1. Identify the JavaScript function bound to the “Copy All” button.
2. Extend the function to:
   - Capture the current clipboard HTML string.
   - Append labeled Q&A blocks extracted from the session transcript (use segment IDs if present).
   - Serialize the combined string to JSON: `{ "clipboard": "...", "segments": [{ "type": "question", "text": "..." }, { "type": "answer", "text": "..." }, …] }`.
3. Send a `POST` request to the server endpoint `/save-clipboard` with the JSON payload.

### 2. Server-side Changes
1. Determine whether persistence logic lives in `server.py` or `menu.py`.
2. Add a new route, e.g., `POST /save-clipboard`, that:
   - Parses the incoming JSON.
   - Appends the payload to a durable store (e.g., `data/clipboard_store.json` or a tiny SQLite DB).
   - Returns a success status and the stored identifier.
3. Optionally create a `GET /load-clipboard` endpoint to retrieve stored segments in order for the client to display.

### 3. Verification
- Click **Copy All** and inspect the network tab – payload should match the expected JSON structure.
- Query the server endpoint to confirm the payload is stored with correct labeling and order.
- Refresh the client’s “History” view – the saved segments should appear when fetching the server data.

## File Locations
- Client: `templates/static recorder.html`
- Server candidate: `server.py` **or** `menu.py` (check imports for existing API routes).
