# Sunrise Interiors — AI-Powered Outbound Voice Call System

An enterprise-grade outbound voice calling platform built with **Flask**, **Vapi AI**, and **Twilio PSTN**. Designed for **Sunrise Interiors**, the system eliminates prospective client drop-off by automatically triggering an AI voice agent (**Aanya**) the moment a user submits an inquiry on the website.

**Live Application Demo:** [https://voice-call-agent-f3yb.onrender.com](https://voice-call-agent-f3yb.onrender.com)
**AI Call Portal:** [https://voice-call-agent-f3yb.onrender.com/call](https://voice-call-agent-f3yb.onrender.com/call)

The AI agent places a real cellular phone call to the user within seconds, conducts a natural qualification dialogue in **Hindi, Hinglish, or English**, and streams live conversation transcripts, call status updates, and structured 2x2 lead analytics to a web interface.


---

## Technical Overview & Features

- **Architectural Design System**: Clean, white-theme layout with Google Fonts (*Outfit* and *Plus Jakarta Sans*), glassmorphic containers, and responsive UI components.
- **Multi-Page Routing**:
  - `/` — **Landing Page**: Features a 30-second flat budget estimator, signature design style explorer (*Modern Japandi*, *Contemporary Indian Luxury*, *Warm Scandinavian*, *Neoclassical Opulence*), and brand statistics.
  - `/call` — **AI Voice Portal**: Dedicated portal containing the outbound call trigger form, live audio wave visualizer, real-time transcript speech bubbles, lead qualification summary, and call history logs.
- **Vapi AI Native Voice Engine**: Powered by Vapi's native Indian voice model (*Naina*) with sub-second response latency.
- **Twilio PSTN Gateway Integration**: Connected via Twilio carrier SIP trunking to dial cellular mobile numbers (`+91...`).
- **Conversational Prompt Optimization**: Enforces strict turn-taking rules (1–2 short sentences per turn, <20 words max) to eliminate long monologues and maintain natural phone conversational pacing.
- **Post-Call Lead Qualification**: Runs post-call analysis to summarize four key metrics (*Work required*, *Start timeline*, *Meeting agreement*, *Time slot preference*).
- **Persistence Layer**: Atomic upsert transactions persisted to a local `call_history.json` datastore.

---

## Architectural Migration: Bland AI to Vapi AI

The system was initially built using **Bland AI** and subsequently migrated to **Vapi AI** combined with **Twilio PSTN**.

### Rationale for Migration

1. **Superior Hindi and Hinglish Accent Synthesis**
   Bland AI's internal speech synthesis generated flatter, monotone inflections when handling Indian names and Hinglish phrases. Migrating to Vapi AI enabled utilizing **Vapi's native voice model** (*Naina*), delivering natural phonetic pronunciation, realistic intonations, and authentic conversational fillers (*"haan"*, *"theek hai"*).


2. **Carrier Control via Twilio PSTN Integration**
   Bland AI provided limited control over outbound caller IDs and underlying carrier trunks. Vapi AI allowed bridging a dedicated **Twilio PSTN gateway**, giving complete visibility over SIP signaling, carrier routing, and call log diagnostics for Indian cellular networks.

3. **Sub-500ms Response Latency and Barge-In Detection**
   Vapi AI's orchestration architecture provided sub-500ms turn-taking latency. It natively handles **barge-in detection**—if a user interrupts the AI mid-sentence, Vapi instantly halts audio playback and processes the caller's input without clipping.

---

## System Architecture

```
                                  +------------------------------------+
                                  |   Client Browser (index / call)    |
                                  +------------------------------------+
                                                     |
                                                     | HTTP POST /api/call
                                                     v
                                  +------------------------------------+
                                  |     Flask Server (app.py)          |
                                  +------------------------------------+
                                                     |
                                                     | REST API Request (Bearer Token)
                                                     v
                                  +------------------------------------+
                                  |      Vapi AI Voice Orchestration   |
                                  |   (ElevenLabs Indian Voice Engine) |
                                  +------------------------------------+
                                                     |
                                                     | PSTN Carrier Protocol
                                                     v
                                  +------------------------------------+
                                  |       Twilio Telephony Trunk       |
                                  +------------------------------------+
                                                     |
                                                     | Outbound Cellular Call
                                                     v
                                  +------------------------------------+
                                  |         User's Mobile Phone        |
                                  +------------------------------------+
```

---

## Project Structure

```
Voice Call Agent/
├── app.py                  # Main Flask application server & API routes
├── requirements.txt        # Python dependencies (Flask, CORS, Requests, Gunicorn)
├── Procfile                # Production process file
├── .env                    # Environment configuration
├── .env.example            # Environment template
├── call_history.json       # Persistent local JSON record store
├── templates/
│   ├── index.html          # Main luxury landing page
│   └── call.html           # Dedicated AI Voice Calling Hub
└── venv/                   # Virtual environment
```

---

## API Reference

### Application Routes
- `GET /` — Renders the main Sunrise Interiors landing page.
- `GET /call` — Renders the dedicated AI Voice Calling Portal.

### REST API Endpoints
- `POST /api/call` — Accepts `{ "name": "Rahul", "phone_number": "+919876543210" }` and dispatches an outbound call.
- `GET /api/call/<call_id>` — Fetches call status, duration, and real-time transcript.
- `POST /api/call/<call_id>/analyze` — Parses transcript data and returns structured 2x2 lead qualification answers.
- `GET /api/history` — Returns all stored call records, newest first.
- `POST /api/history/refresh` — Scans active calls and backfills transcripts/durations upon page reload.

---

## Setup and Installation

### Prerequisites
- Python 3.9 or higher
- Vapi AI Account
- Twilio Account (with configured Account SID, Auth Token, and Phone Number)

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/Voice-Call-Agent.git
   cd "Voice Call Agent"
   ```

2. **Configure virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the project root:
   ```env
   TELEPHONY_PROVIDER=vapi
   VAPI_API_KEY=your_vapi_private_api_key
   VAPI_ASSISTANT_ID=your_vapi_assistant_id
   VAPI_PHONE_NUMBER_ID=your_vapi_twilio_phone_number_id
   PORT=5001
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```
   Access the application at `http://127.0.0.1:5001`.

---

## License

Distributed under the MIT License. Developed for Sunrise Interiors AI Voice Automation.
