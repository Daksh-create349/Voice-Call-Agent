> [!WARNING]
> This is a testing and demonstration project. The live demo may stop functioning once the free Bland AI credits run out. :( If calls stop going through, it is likely the API credits have been exhausted.

# Voice Agent — AI-Powered Outbound Call System


A production-ready outbound voice calling system built with Flask and the Bland AI telephony platform. When a prospective customer submits their phone number through a web form, the system immediately triggers an AI voice agent that calls them back, holds a natural conversation, and saves the full call record, transcript, and structured lead analysis to persistent local storage.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [System Flow](#system-flow)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Setup and Installation](#setup-and-installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [How the AI Agent Behaves](#how-the-ai-agent-behaves)
- [Call History and Persistence](#call-history-and-persistence)
- [Transcript and Lead Analysis](#transcript-and-lead-analysis)
- [Known Behaviours and Edge Cases](#known-behaviours-and-edge-cases)

---

## Overview

This system eliminates the delay between a customer expressing interest and receiving a callback. The moment a visitor submits their phone number on the landing page, a Bland AI voice agent places a real phone call to that number within seconds. The agent conducts a structured yet natural conversation, qualifies the lead, and attempts to schedule a follow-up meeting.

Everything that happens during the call is captured: the full conversation transcript, call duration, and a machine-generated lead summary answering four specific qualification questions. All data is written to a local JSON file and displayed live in the browser interface.

---

## Architecture

```
Browser (index.html)
       |
       | HTTP POST /api/call
       v
Flask Server (app.py)
       |
       | POST https://api.bland.ai/v1/calls
       v
Bland AI Platform
       |
       | Places outbound call to customer's phone
       v
Customer's Phone
       |
       | Call completes
       v
Bland AI Platform (stores recording + transcript)
       |
       | GET https://api.bland.ai/v1/calls/{call_id}
       v
Flask Server (polls from browser, saves to call_history.json)
       |
       | POST https://api.bland.ai/v1/calls/{call_id}/analyze
       v
Bland AI Platform (runs post-call NLP analysis)
       |
       | Returns structured answers to 4 lead questions
       v
Flask Server (merges into call record, returns to browser)
       |
       | Rendered in browser as transcript + lead summary card
       v
Browser (index.html)
```

---

## System Flow

### Step 1 — Form Submission

The user visits the root URL and sees a simple card with two input fields: an optional name field and a required phone number field. On submit, the browser sends a POST request to `/api/call` with a JSON body containing `name` and `phone_number`.

### Step 2 — Phone Number Normalisation

Before the call is dispatched, the Flask server normalises the phone number. Any spaces and dashes are stripped. If the number does not begin with a `+` country code, the system assumes it is a 10-digit Indian mobile number and prepends `+91`. This makes the form tolerant of various input formats without requiring the user to type an international prefix.

### Step 3 — Call Dispatch to Bland AI

The server constructs a payload and sends it to the Bland AI `/v1/calls` endpoint via an HTTP POST. The payload includes:

- The normalised phone number
- The full task prompt that defines the agent's persona, goals, and conversation strategy
- A dynamic `first_sentence` that either addresses the caller by name or uses a generic greeting
- The selected voice ID loaded from the environment
- Language set to `hi` (which applies an Indian English voice profile)
- Flags for behaviour: wait for the person to finish speaking before responding, allow interruptions, and record the call
- A maximum call duration of 3 minutes

Bland AI queues the call and returns a `call_id` immediately. The Flask server saves an initial record to `call_history.json` with status `"initiated"`.

### Step 4 — Status Polling

Once the browser receives the `call_id`, it begins polling the `/api/call/{call_id}` endpoint every 5 seconds for up to 3 minutes (36 poll attempts). On each poll, the Flask server calls the Bland AI GET endpoint and inspects the response.

Completion is detected by checking two fields: `status === "completed"` or `queue_status === "complete"`. Bland AI may set either field depending on how the call ended, so both are evaluated.

The browser status bar updates with elapsed time and the current call state on each poll. When completion is detected, the frontend stops polling, updates the status to success, and proceeds to render the transcript.

### Step 5 — Transcript Rendering

When completion is detected, the GET response includes a `transcripts` array. Each item in the array contains a `user` field (either `"assistant"` for the AI agent or `"user"` for the human caller) and a `text` field containing the utterance.

The browser renders these as a two-tone conversation view: the AI agent's lines are labelled and styled in orange, the caller's lines are styled in blue. Empty utterances are filtered out before rendering.

### Step 6 — Lead Analysis

Immediately after the transcript is rendered, the browser fires a POST request to `/api/call/{call_id}/analyze`. This endpoint calls the Bland AI `/v1/calls/{call_id}/analyze` endpoint with a goal description and a list of four structured questions:

1. What work do they want done on their flat? (string)
2. How soon do they want to start? (string)
3. Did they agree to a designer meeting? (boolean)
4. What day or time preference did they give? (string)

Bland AI processes the transcript using natural language understanding and returns an `answers` array with one answer per question, in the same order. The Flask server maps these answers to their labels and saves the structured analysis to the call record. The browser renders the four answers in a 2x2 grid card labelled "Lead summary". Boolean answers are displayed as green "Yes" or red "No" with tick and cross marks.

### Step 7 — History Panel

Every time the page loads, the browser calls `POST /api/history/refresh`. This endpoint scans `call_history.json` for any records still marked `"initiated"` — which indicates the poll window expired before the call completed — and re-fetches their status from Bland AI to backfill the transcript and call length. This ensures that calls which took longer than the polling window to complete are still recovered and displayed correctly.

The history panel on the right side of the page renders all past calls in reverse chronological order. Each card shows the caller's name, phone number, timestamp, status badge, call duration, the four lead analysis answers, and a collapsible transcript accordion.

---

## Project Structure

```
.
├── app.py                  Main Flask application server
├── requirements.txt        Python dependencies
├── .env                    Environment variables (not committed to git)
├── .env.example            Template showing required variable names
├── .gitignore              Files excluded from version control
├── call_history.json       Persistent call records (auto-created at runtime)
└── templates/
    └── index.html          Single-page frontend served by Flask
```

---

## API Reference

### GET /

Serves the main HTML page.

---

### POST /api/call

Triggers a new outbound call.

**Request body (JSON)**

| Field | Type | Required | Description |
|---|---|---|---|
| phone_number | string | Yes | Caller's phone number, any common format |
| name | string | No | Caller's name, used to personalise the opening line |

**Response**

Returns Bland AI's raw response including the `call_id` on success. Returns `400` if `phone_number` is missing. Returns `500` on Bland API errors.

---

### GET /api/call/{call_id}

Fetches the current status, transcript, and call length for a given call.

**Response**

```json
{
  "status": "completed",
  "call_length": 2.48,
  "transcript": [
    { "speaker": "assistant", "text": "Hi, am I speaking with..." },
    { "speaker": "user", "text": "Yes?" }
  ],
  "raw": { ... }
}
```

When the call is detected as complete, the record in `call_history.json` is immediately updated with the transcript and call length.

---

### POST /api/call/{call_id}/analyze

Runs post-call NLP analysis via Bland AI and returns structured lead data.

**Response**

```json
{
  "answers": [
    "Full home interior",
    "In the next month",
    true,
    "Weekday morning"
  ]
}
```

The four answers correspond to the four lead qualification questions in order. The structured result is saved into the call record under `analysis`.

---

### GET /api/history

Returns the full list of call records from `call_history.json`, newest first.

---

### POST /api/history/refresh

Scans all `"initiated"` records and re-fetches their status from Bland AI. Backfills any calls that completed after the poll window expired. Returns the updated record list.

---

## Setup and Installation

**Prerequisites**

- Python 3.9 or higher
- A Bland AI account with an API key
- A Bland AI voice ID for the agent

**Clone or copy the project**

```bash
cd "Voice Call Agent"
```

**Create and activate a virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Install dependencies**

```bash
pip install -r requirements.txt
```

**Create your environment file**

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials. See the Configuration section below.

## Getting Your Bland AI Credentials

This project uses Bland AI to place real phone calls. You need two things from Bland AI: an API key and a voice ID. Both are free to obtain and the platform provides free credits to get started.

### Step 1 — Create a Bland AI Account

Go to https://app.bland.ai and sign up for a free account. You will need to verify your email address before you can access the dashboard.

### Step 2 — Get Your API Key

1. Once logged in, open the left sidebar and click on your account name or the settings icon.
2. Navigate to the "API Keys" or "Developer" section.
3. Click "Create new key" or "Generate API key".
4. Copy the key immediately. It will only be shown once in full. The key starts with `org_`.
5. Paste this value as `BLAND_API_KEY` in your `.env` file.

### Step 3 — Choose a Voice ID

Bland AI provides a library of pre-built AI voices. To find a voice that suits the agent persona:

1. In the Bland AI dashboard, go to the "Voices" section in the sidebar.
2. Browse the available voices and use the play button to preview each one.
3. Select a voice that sounds natural and appropriate for a warm, conversational agent.
4. Click on the voice to open its detail page. The voice ID is shown on this page and looks like a UUID, for example: `095a1518-ecdf-4870-a5ff-c74b43a08764`.
5. Copy this ID and paste it as `BLAND_VOICE` in your `.env` file.

Alternatively, you can retrieve all available voices programmatically by calling:

```
GET https://api.bland.ai/v1/voices
Authorization: your_api_key
```

### Step 4 — Note on Free Credits

Bland AI provides a limited number of free credits when you sign up. Each outbound call consumes credits based on call duration. Once the free credits are exhausted, calls will fail unless you add billing information to your account. The application will return an error from the `/api/call` endpoint when this happens.

---

## Configuration


The application reads all secrets and settings from the `.env` file in the project root. Never commit this file to version control.

| Variable | Description |
|---|---|
| BLAND_API_KEY | Your Bland AI organisation API key |
| BLAND_VOICE | The Bland AI voice ID to use for the agent |
| PORT | The port Flask listens on (default: 5000) |

**Example `.env`**

```
BLAND_API_KEY=org_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
BLAND_VOICE=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PORT=5001
```

Note: On macOS, port 5000 is used by the AirPlay Receiver service by default. Either disable AirPlay Receiver in System Settings under General, AirDrop and Handoff, or set PORT to 5001 in your `.env` file.

---

## Running the Application

**Start the server**

```bash
source venv/bin/activate
python app.py
```

**Open the browser**

Navigate to `http://127.0.0.1:5001` (or whichever port is set in `.env`).

**Stop the server**

Press `Ctrl + C` in the terminal.

Flask runs in debug mode with the auto-reloader active, so any changes to `app.py` or the HTML template are picked up immediately without restarting.

---

## How the AI Agent Behaves

The agent is named Aanya and operates as a callback specialist. Her full personality, goals, and conversational strategy are defined in the `TASK` constant in `app.py`. The key behavioural rules are:

**Opening the call**

If the caller's name was provided on the form, the first sentence asks to confirm the name before introducing the purpose of the call. If no name was provided, a generic warm opening is used.

**Handling availability**

If the caller says it is not a good time, the agent briefly apologises, asks when to call back, thanks them, and ends the call. She does not push further.

**Qualifying the lead**

If the caller is available, the agent asks about the nature of the work they want done (full interior, specific rooms, renovation), and when they are hoping to start. Based on the response, she offers a free, no-obligation meeting with a designer.

**Scheduling**

If the caller agrees to the meeting, she asks for a rough time preference: this week or next, weekday or weekend, morning or evening. She confirms that someone from the team will follow up on WhatsApp to lock the exact slot.

**Language mirroring**

The agent mirrors the caller's language throughout the call. If the caller responds in English, the agent continues in English. If the caller switches to Hindi or a Hindi-English mix, the agent naturally follows. This is built into the task prompt; no additional configuration is required.

**Tone**

The agent uses short, natural sentences. She uses fillers like "got it", "no worries", and "makes sense" where appropriate. The energy is warm and conversational, not scripted or robotic.

---

## Call History and Persistence

All call data is stored in `call_history.json` in the project root. This file is created automatically on first use. Records are keyed by `call_id` and updated in-place across three stages:

**Stage 1 — Initiated**

Written immediately when the call is dispatched. Contains name, phone number, timestamp, and status `"initiated"`.

**Stage 2 — Completed**

Written when the poll detects completion. Adds status `"completed"`, call length in seconds, and the full transcript array.

**Stage 3 — Analysed**

Written after the lead analysis endpoint returns. Adds an `analysis` dictionary mapping each question label to its answer.

The refresh endpoint (`POST /api/history/refresh`) is called on every page load. It finds any records still in `"initiated"` state and re-fetches them from Bland AI. This recovers calls that completed after the 3-minute poll window expired, ensuring no data is permanently lost.

The history file is listed in `.gitignore` because it contains personally identifiable information including names and phone numbers.

---

## Transcript and Lead Analysis

Bland AI returns the call transcript as an array of utterance objects under the key `transcripts`. Each object contains:

- `user`: either `"assistant"` (the AI agent) or `"user"` (the human caller)
- `text`: the spoken text of that turn
- `created_at`: the timestamp of the utterance

The server normalises this into a consistent format before saving and returning it. Empty utterances are filtered out.

The lead analysis is powered by Bland AI's post-call analysis feature. The system sends a goal statement and four questions. Bland AI reads the transcript and returns one answer per question. String answers are returned as-is. Boolean answers are `true` or `false` and rendered in the UI as green or red indicators.

---

## Known Behaviours and Edge Cases

**Call detected as complete but transcript is empty**

This can happen if the call was placed but the person did not answer, or if the call was extremely short. The UI will show "No transcript available" in this case.

**Poll window expires before call completes**

If the call takes longer than 3 minutes and the poll window expires, the browser shows a message saying the transcript will appear once the call ends. On the next page load, the refresh endpoint will recover the completed transcript and display it in the history panel.

**Phone number without country code**

Any number that does not begin with `+` is assumed to be a 10-digit Indian mobile number and `+91` is prepended automatically. To call numbers in other countries, include the full international dialling code with a `+` prefix when entering the number.

**macOS port 5000 conflict**

macOS reserves port 5000 for the AirPlay Receiver service. Set `PORT=5001` in `.env` or disable AirPlay Receiver in System Settings to use port 5000.
