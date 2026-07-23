# Sunrise Interiors — AI-Powered Outbound Voice Call System

A production-ready, multi-page outbound voice calling platform built with **Flask**, **Vapi AI**, **ElevenLabs**, and **Twilio PSTN**. Designed for **Sunrise Interiors**, the system eliminates lead drop-off by instantly triggering an AI voice consultant (**Aanya**) the moment a prospective client submits their phone number. 

The AI agent dials the user's mobile phone within seconds, conducts a natural, concise qualification conversation in **Hindi, Hinglish, or English**, and streams live transcripts, call audio waveforms, and structured 2x2 lead analytics to a modern web interface.

---

## 📸 Key Features

- **Luxury Light-Mode Design System**: Built with Google Fonts (*Outfit* + *Plus Jakarta Sans*), warm porcelain ivory aesthetics, and glassmorphic UI components.
- **Multi-Page Architecture**:
  - `/` — **Interactive Hero Landing Page**: Features a 30-second budget estimator, signature design style explorer (*Modern Japandi*, *Contemporary Indian Luxury*, *Warm Scandinavian*, *Neoclassical Opulence*), and client statistics.
  - `/call` — **AI Voice Calling Portal**: Dedicated portal with instant call submission form, live audio wave visualizer, real-time transcript speech bubbles, lead qualification grid, and history logs.
- **Vapi AI + ElevenLabs Speech Engine**: Powered by ElevenLabs' Indian voice model (*Aditi*) with sub-second response latency.
- **Twilio PSTN Gateway**: Connected via Twilio carrier integration to dial real cellular mobile numbers (`+91...`).
- **Concise Turn-Taking Prompt Directives**: Enforces 1–2 short sentences per turn (<20 words) and single-question hand-offs to eliminate robot monologues.
- **Post-Call Lead Qualification**: Runs post-call NLP analysis to summarize 4 key lead metrics (*Work required*, *Start timeline*, *Meeting agreement*, *Time slot preference*).
- **Persistent Data Store**: Atomic upsert transactions persisted to `call_history.json`.
- **Cloud Deployment Ready**: Pre-configured with `gunicorn`, `Procfile`, and 100% free deployment support on **Render.com**.

---

## 🏗️ System Architecture

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

## 📁 Project Structure

```
Voice Call Agent/
├── app.py                  # Main Flask application server & API routes
├── requirements.txt        # Python dependencies (Flask, CORS, Requests, Gunicorn)
├── Procfile                # Cloud deployment process file for Render / Heroku
├── .env                    # Environment variables (Vapi, Twilio, Bland credentials)
├── .env.example            # Environment template file
├── call_history.json       # Persistent local JSON record store
├── templates/
│   ├── index.html          # Main luxury landing page with interactive widgets
│   └── call.html           # Dedicated AI Voice Calling Hub & live transcript portal
└── venv/                   # Virtual environment
```

---

## 🚀 API Reference

### Page Routes
- `GET /` — Renders the main Sunrise Interiors luxury landing page.
- `GET /call` — Renders the dedicated AI Voice Calling Portal.

### API Endpoints
- `POST /api/call` — Accepts `{ "name": "Rahul", "phone_number": "+919876543210" }` and dispatches an outbound Vapi/Bland call.
- `GET /api/call/<call_id>` — Fetches live call status, audio duration, and real-time transcript.
- `POST /api/call/<call_id>/analyze` — Parses transcript data and returns structured 2x2 lead qualification answers.
- `GET /api/history` — Returns all stored call records, newest first.
- `POST /api/history/refresh` — Scans stuck or completed calls and backfills transcripts/durations upon page reload.

---

## ⚙️ Setup and Installation

### 1. Prerequisites
- Python 3.9 or higher
- Vapi AI Account ([vapi.ai](https://vapi.ai))
- Twilio Trial Account ([twilio.com](https://twilio.com))

### 2. Installation
```bash
# Clone repository
git clone https://github.com/your-username/Voice-Call-Agent.git
cd "Voice Call Agent"

# Activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the project root:

```env
TELEPHONY_PROVIDER=vapi

# Vapi Credentials
VAPI_API_KEY=your_vapi_private_api_key
VAPI_ASSISTANT_ID=your_vapi_assistant_id
VAPI_PHONE_NUMBER_ID=your_vapi_twilio_phone_number_id

# Optional Bland AI Fallback
BLAND_API_KEY=org_your_bland_key
BLAND_VOICE=095a1518-ecdf-4870-a5ff-c74b43a08764

PORT=5001
```

### 4. Running Locally
```bash
python app.py
```
Open **[http://127.0.0.1:5001](http://127.0.0.1:5001)** in your browser.

---

## ☁️ 100% Free Cloud Deployment (Render.com)

1. Push your code to GitHub:
   ```bash
   git add .
   git commit -m "Deploy Sunrise Interiors Voice Agent"
   git push origin main
   ```
2. Log into **[Render.com](https://render.com)** → Click **New +** → **Web Service**.
3. Connect your GitHub repository and set:
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
4. Add your `.env` keys under **Environment Variables**.
5. Click **Create Web Service** to receive your live SSL domain (`https://your-app.onrender.com`).

---

## 📄 License

Distributed under the MIT License. Developed for Sunrise Interiors AI Voice Automation.
