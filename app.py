import os
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import requests as http_requests

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)

# Read config from environment
BLAND_API_KEY = os.getenv("BLAND_API_KEY", "")
BLAND_VOICE   = os.getenv("BLAND_VOICE", "")
PORT          = int(os.getenv("PORT", 5000))

BLAND_API_URL = "https://api.bland.ai/v1/calls"
HISTORY_FILE  = Path("call_history.json")

# ── History helpers ────────────────────────────────────────────────────────────

def load_history() -> list:
    """Load all call records from disk."""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_history(records: list) -> None:
    """Persist call records to disk."""
    HISTORY_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def upsert_record(patch: dict) -> None:
    """Insert or merge-update a record keyed on call_id."""
    records = load_history()
    call_id = patch.get("call_id")
    for i, r in enumerate(records):
        if r.get("call_id") == call_id:
            records[i] = {**r, **patch}
            save_history(records)
            return
    records.insert(0, patch)   # newest first
    save_history(records)


# ── Prompt ─────────────────────────────────────────────────────────────────────

TASK = """
You are Aanya, a warm, friendly, and energetic callback specialist for Sunrise Interiors, an interior design company in India.

Context: The person you are calling filled out an enquiry form on the Sunrise Interiors website moments ago about designing their new flat, and shared their phone number so someone could call them back right away — which is what you're doing now.

Start the call by greeting them warmly, introducing yourself by name, mentioning you're calling from Sunrise Interiors about the enquiry they just submitted, and asking if this is a good time to talk for a couple of minutes.

If they say it's not a good time: apologize briefly, ask when would be better to call back, thank them, and end the call politely. Do not push further.

If it is a good time, continue naturally:
1. Ask what kind of work they're looking to get done on their flat — full home interior, specific rooms like kitchen, bedroom, living room, or a renovation — and roughly when they're hoping to start.
2. Based on what they tell you, warmly offer a free, no-obligation meeting with one of Sunrise Interiors' in-house designers so the designer can understand their space and vision better.
3. If they agree, ask for a rough time preference — this week or next, weekday or weekend, morning or evening — and confirm someone from the team will follow up on WhatsApp shortly to lock the exact slot.
4. If they say they're not interested, thank them sincerely and end the call gracefully. Never repeat the pitch or sound disappointed.
5. If they ask about pricing, process, timelines, or the company, answer briefly and naturally in your own words, then gently bring it back to scheduling the meeting.

How to sound and behave:
- This is a real phone conversation, not a script being read aloud. Short, natural sentences. Use fillers like "haan", "theek hai", "got it", "no worries", "makes sense" where they fit.
- Actually listen — if the person interrupts or talks over you, stop immediately, take in what they said, and respond to that before continuing your own points.
- Mirror the caller's language: if they reply in Hindi or Hinglish, switch to that naturally. If they reply in English, stay in English. Never ask which language to use — just follow their lead.
- Keep the energy warm and genuinely excited about design, not a call-center script reader.
- Keep the whole call to roughly 60-90 seconds of talk time — unhurried but efficient.
- This is a warm follow-up to someone who already showed interest, not a cold sales pitch. Never sound pushy or scripted.
"""

ANALYZE_GOAL = "Extract key details from this interior design sales callback"

ANALYZE_QUESTIONS = [
    ["What work do they want done on their flat?", "string"],
    ["How soon do they want to start?",            "string"],
    ["Did they agree to a designer meeting?",      "boolean"],
    ["What day or time preference did they give?", "string"],
]

LEAD_LABELS = [
    "Work required",
    "Start timeline",
    "Agreed to meeting?",
    "Time preference",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def normalize_phone(raw: str) -> str:
    """Strip spaces and dashes; prepend +91 for 10-digit Indian numbers."""
    cleaned = re.sub(r"[\s\-]", "", raw)
    if not cleaned.startswith("+"):
        cleaned = "+91" + cleaned
    return cleaned


def bland_headers() -> dict:
    return {
        "authorization": BLAND_API_KEY,
        "Content-Type":  "application/json",
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main frontend page."""
    return render_template("index.html")


@app.route("/api/history", methods=["GET"])
def get_history():
    """Return all stored call records, newest first."""
    return jsonify(load_history()), 200


@app.route("/api/call", methods=["POST"])
def make_call():
    """Trigger an outbound Bland AI call."""
    data = request.get_json(silent=True) or {}

    phone_raw = data.get("phone_number", "").strip()
    if not phone_raw:
        return jsonify({"error": "phone_number is required."}), 400

    name         = data.get("name", "").strip()
    phone_number = normalize_phone(phone_raw)
    timestamp    = datetime.now(timezone.utc).isoformat()

    if name:
        first_sentence = (
            f"Hi, am I speaking with {name}? "
            "This is Aanya calling from Sunrise Interiors, about the enquiry you just submitted "
            "on our website — is this an okay time to talk for a couple of minutes?"
        )
    else:
        first_sentence = (
            "Hi there, this is Aanya calling from Sunrise Interiors, about the enquiry you just "
            "submitted on our website — is this an okay time to talk for a couple of minutes?"
        )

    payload = {
        "phone_number":      phone_number,
        "task":              TASK.strip(),
        "first_sentence":    first_sentence,
        "voice":             BLAND_VOICE,
        "language":          "hi",
        "wait_for_greeting": True,
        "block_interruptions": False,
        "max_duration":      3,
        "record":            True,
        "request_data":      {"name": name},
        "metadata":          {"name": name, "timestamp": timestamp},
    }

    try:
        response   = http_requests.post(BLAND_API_URL, json=payload, headers=bland_headers(), timeout=15)
        bland_data = response.json()

        if response.ok and bland_data.get("call_id"):
            upsert_record({
                "call_id":    bland_data["call_id"],
                "name":       name,
                "phone":      phone_number,
                "initiated_at": timestamp,
                "status":     "initiated",
                "call_length": None,
                "transcript": [],
                "analysis":   None,
            })

        return jsonify(bland_data), response.status_code

    except http_requests.exceptions.Timeout:
        return jsonify({"error": "Request to Bland AI timed out. Please try again."}), 500
    except http_requests.exceptions.RequestException as exc:
        return jsonify({"error": f"Failed to reach Bland AI: {str(exc)}"}), 500
    except Exception as exc:
        return jsonify({"error": f"Unexpected error: {str(exc)}"}), 500


@app.route("/api/history/refresh", methods=["POST"])
def refresh_history():
    """Re-fetch any 'initiated' calls from Bland to backfill transcript/status."""
    records = load_history()
    updated = 0
    for r in records:
        if r.get("status") != "initiated":
            continue
        call_id = r.get("call_id")
        if not call_id:
            continue
        try:
            resp = http_requests.get(f"{BLAND_API_URL}/{call_id}", headers=bland_headers(), timeout=10)
            raw  = resp.json()

            transcript_raw = raw.get("transcripts") or []
            transcript = [
                {"speaker": u.get("user", "unknown"), "text": u.get("text", "")}
                for u in transcript_raw if u.get("text", "").strip()
            ] if isinstance(transcript_raw, list) else (raw.get("concatenated_transcript") or "")

            status       = raw.get("status") or ""
            queue_status = raw.get("queue_status") or ""
            call_length  = raw.get("call_length") or raw.get("corrected_duration")
            is_done      = status.lower() == "completed" or queue_status.lower() == "complete"

            if is_done:
                upsert_record({
                    "call_id":      call_id,
                    "status":       "completed",
                    "call_length":  call_length,
                    "transcript":   transcript,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
                updated += 1
        except Exception:
            continue

    return jsonify({"refreshed": updated, "records": load_history()}), 200


@app.route("/api/call/<call_id>", methods=["GET"])
def get_call(call_id):
    """Fetch status, transcript, and duration for a Bland AI call."""
    try:
        response = http_requests.get(
            f"{BLAND_API_URL}/{call_id}",
            headers=bland_headers(),
            timeout=15,
        )
        raw = response.json()

        # Bland uses `transcripts` (list of utterances)
        transcript_raw = raw.get("transcripts") or []
        if isinstance(transcript_raw, list):
            transcript = [
                {"speaker": u.get("user", "unknown"), "text": u.get("text", "")}
                for u in transcript_raw
                if u.get("text", "").strip()
            ]
        else:
            # concatenated_transcript fallback
            ct = raw.get("concatenated_transcript") or ""
            transcript = ct  # plain string

        status        = raw.get("status") or ""
        queue_status  = raw.get("queue_status") or ""
        call_length   = raw.get("call_length") or raw.get("corrected_duration")

        # Bland marks completion via status=completed OR queue_status=complete
        is_done = status.lower() == "completed" or queue_status.lower() == "complete"

        if is_done:
            upsert_record({
                "call_id":      call_id,
                "status":       "completed",
                "call_length":  call_length,
                "transcript":   transcript,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })

        return jsonify({
            "status":      "completed" if is_done else status,
            "call_length": call_length,
            "transcript":  transcript,
            "raw":         raw,
        }), response.status_code

    except http_requests.exceptions.Timeout:
        return jsonify({"error": "Request to Bland AI timed out."}), 500
    except http_requests.exceptions.RequestException as exc:
        return jsonify({"error": f"Failed to reach Bland AI: {str(exc)}"}), 500
    except Exception as exc:
        return jsonify({"error": f"Unexpected error: {str(exc)}"}), 500


@app.route("/api/call/<call_id>/analyze", methods=["POST"])
def analyze_call(call_id):
    """Run Bland's post-call analysis and persist the structured lead data."""
    payload = {
        "goal":      ANALYZE_GOAL,
        "questions": ANALYZE_QUESTIONS,
    }

    try:
        response = http_requests.post(
            f"{BLAND_API_URL}/{call_id}/analyze",
            json=payload,
            headers=bland_headers(),
            timeout=20,
        )
        result  = response.json()
        answers = result.get("answers", [])

        if answers:
            analysis = {
                LEAD_LABELS[i]: answers[i]
                for i in range(min(len(LEAD_LABELS), len(answers)))
            }
            upsert_record({"call_id": call_id, "analysis": analysis})

        return jsonify(result), response.status_code

    except http_requests.exceptions.Timeout:
        return jsonify({"error": "Analysis request timed out."}), 500
    except http_requests.exceptions.RequestException as exc:
        return jsonify({"error": f"Failed to reach Bland AI: {str(exc)}"}), 500
    except Exception as exc:
        return jsonify({"error": f"Unexpected error: {str(exc)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
