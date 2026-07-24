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
TELEPHONY_PROVIDER = os.getenv("TELEPHONY_PROVIDER", "vapi").strip().lower()

# Vapi Config
VAPI_API_KEY          = os.getenv("VAPI_API_KEY", "").strip()
VAPI_ASSISTANT_ID     = os.getenv("VAPI_ASSISTANT_ID", "").strip()
VAPI_PHONE_NUMBER_ID  = os.getenv("VAPI_PHONE_NUMBER_ID", "").strip()
VAPI_API_URL           = "https://api.vapi.ai/call/phone"


# Bland Config
BLAND_API_KEY      = os.getenv("BLAND_API_KEY", "").strip()
BLAND_VOICE        = os.getenv("BLAND_VOICE", "").strip()
BLAND_API_URL      = "https://api.bland.ai/v1/calls"

PORT               = int(os.getenv("PORT", 5001))
# Use /tmp folder on Vercel / serverless environments to prevent read-only filesystem errors
IS_SERVERLESS = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
HISTORY_FILE  = Path("/tmp/call_history.json") if IS_SERVERLESS else Path("call_history.json")


# ── History helpers ────────────────────────────────────────────────────────────

def load_history() -> list:
    """Load all call records from disk or /tmp."""
    for path in [HISTORY_FILE, Path("/tmp/call_history.json"), Path("call_history.json")]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
    return []


def save_history(records: list) -> None:
    """Persist call records safely (with /tmp fallback for read-only serverless filesystems)."""
    for path in [HISTORY_FILE, Path("/tmp/call_history.json")]:
        try:
            path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
            return
        except Exception:
            continue



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


# ── Concise & Punchy System Prompt ─────────────────────────────────────────────

TASK = """
You are Aanya, a warm, friendly callback specialist for Sunrise Interiors, India.

CONTEXT:
The caller just submitted an enquiry form on your website for flat interior design. You are placing an instant callback.

STRICT CONVERSATIONAL RULES (MUST FOLLOW):
1. CRITICAL: Keep EVERY response to 1 or 2 SHORT sentences maximum (under 15-20 words). NEVER monologue or explain long details.
2. Ask ONLY ONE question at a time, then STOP talking immediately and listen.
3. Mirror the user's language seamlessly (Hindi, Hinglish, or English). Use natural Indian fillers like "haan", "theek hai", "got it", "makes sense".

CONVERSATION STEPS:
- STEP 1 (Greeting): Warmly say who you are, mention the website enquiry, and ask: "Is this a good time to chat for a minute?"
- STEP 2 (Requirement): Ask what work they want done (e.g. 2BHK/3BHK full home, modular kitchen, or bedroom) and when they plan to start.
- STEP 3 (Designer Meeting): Offer a free 3D designer consultation. If they agree, ask their preferred slot (weekday/weekend, morning/evening).
- STEP 4 (Wrap up): Confirm WhatsApp follow-up and politely end the call.

If they say "Not a good time" or "Not interested": Say "No worries at all, thank you!" and end gracefully.
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


def vapi_headers() -> dict:
    return {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type":  "application/json",
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main landing page."""
    return render_template("index.html")


@app.route("/call")
def call_page():
    """Serve the AI calling portal page."""
    return render_template("call.html")


@app.route("/api/history", methods=["GET"])
def get_history():
    """Return all stored call records, newest first."""
    return jsonify(load_history()), 200


@app.route("/api/call", methods=["POST"])
def make_call():
    """Trigger an outbound call via Vapi AI or Bland AI."""
    data = request.get_json(silent=True) or {}

    phone_raw = data.get("phone_number", "").strip()
    if not phone_raw:
        return jsonify({"error": "phone_number is required."}), 400

    name         = data.get("name", "").strip()
    phone_number = normalize_phone(phone_raw)
    timestamp    = datetime.now(timezone.utc).isoformat()

    # ── VAPI AI ROUTE ──
    if TELEPHONY_PROVIDER == "vapi":
        if not VAPI_API_KEY or not VAPI_ASSISTANT_ID:
            return jsonify({"error": "VAPI_API_KEY or VAPI_ASSISTANT_ID missing in .env"}), 400

        payload = {
            "assistantId": VAPI_ASSISTANT_ID,
            "customer": {
                "number": phone_number,
                "name":   name or "Customer"
            }
        }
        if VAPI_PHONE_NUMBER_ID:
            payload["phoneNumberId"] = VAPI_PHONE_NUMBER_ID


        try:
            response  = http_requests.post(VAPI_API_URL, json=payload, headers=vapi_headers(), timeout=15)
            vapi_data = response.json()
            call_id   = vapi_data.get("id") or vapi_data.get("call_id")

            if response.ok and call_id:
                upsert_record({
                    "call_id":      call_id,
                    "provider":     "vapi",
                    "name":         name,
                    "phone":        phone_number,
                    "initiated_at": timestamp,
                    "status":       "initiated",
                    "call_length":  None,
                    "transcript":   [],
                    "analysis":     None,
                })
                return jsonify({"call_id": call_id, "status": "initiated", "raw": vapi_data}), 200
            else:
                err_msg = vapi_data.get("message") or vapi_data.get("error") or str(vapi_data)
                return jsonify({"error": f"Vapi Error: {err_msg}"}), response.status_code

        except Exception as exc:
            return jsonify({"error": f"Failed to reach Vapi API: {str(exc)}"}), 500

    # ── BLAND AI ROUTE ──
    else:
        if name:
            first_sentence = (
                f"Namaste {name}! This is Aanya calling from Sunrise Interiors regarding the interior design enquiry you submitted on our website — is this a good time to chat for a minute?"
            )
        else:
            first_sentence = (
                "Namaste! This is Aanya calling from Sunrise Interiors regarding the interior design enquiry you submitted on our website — is this a good time to chat for a minute?"
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
                    "call_id":      bland_data["call_id"],
                    "provider":     "bland",
                    "name":         name,
                    "phone":        phone_number,
                    "initiated_at": timestamp,
                    "status":       "initiated",
                    "call_length":  None,
                    "transcript":   [],
                    "analysis":     None,
                })

            return jsonify(bland_data), response.status_code
        except Exception as exc:
            return jsonify({"error": f"Failed to reach Bland AI: {str(exc)}"}), 500


@app.route("/api/history/refresh", methods=["POST"])
def refresh_history():
    """Re-fetch any 'initiated' calls from Vapi/Bland to backfill transcript/status."""
    records = load_history()
    updated = 0
    for r in records:
        if r.get("status") != "initiated":
            continue
        call_id  = r.get("call_id")
        provider = r.get("provider", "vapi" if TELEPHONY_PROVIDER == "vapi" else "bland")
        if not call_id:
            continue

        try:
            if provider == "vapi":
                resp = http_requests.get(f"https://api.vapi.ai/call/{call_id}", headers=vapi_headers(), timeout=10)
                raw  = resp.json()
                status = (raw.get("status") or "").lower()
                is_done = status in ["ended", "completed"]

                if is_done:
                    transcript = parse_vapi_transcript(raw)
                    duration   = parse_vapi_duration(raw)
                    upsert_record({
                        "call_id":      call_id,
                        "status":       "completed",
                        "call_length":  duration,
                        "transcript":   transcript,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    })
                    updated += 1

            else:
                resp = http_requests.get(f"{BLAND_API_URL}/{call_id}", headers=bland_headers(), timeout=10)
                raw  = resp.json()
                status       = raw.get("status") or ""
                queue_status = raw.get("queue_status") or ""
                is_done      = status.lower() == "completed" or queue_status.lower() == "complete"

                if is_done:
                    transcript_raw = raw.get("transcripts") or []
                    transcript = [
                        {"speaker": u.get("user", "unknown"), "text": u.get("text", "")}
                        for u in transcript_raw if u.get("text", "").strip()
                    ] if isinstance(transcript_raw, list) else (raw.get("concatenated_transcript") or "")

                    upsert_record({
                        "call_id":      call_id,
                        "status":       "completed",
                        "call_length":  raw.get("call_length") or raw.get("corrected_duration"),
                        "transcript":   transcript,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    })
                    updated += 1
        except Exception:
            continue

    return jsonify({"refreshed": updated, "records": load_history()}), 200


@app.route("/api/call/<call_id>", methods=["GET"])
def get_call(call_id):
    """Fetch status, transcript, and duration for a Vapi or Bland AI call."""
    records = load_history()
    record  = next((r for r in records if r.get("call_id") == call_id), {})
    provider = record.get("provider", TELEPHONY_PROVIDER)

    if provider == "vapi":
        try:
            # If fallback was already triggered for this call, immediately return
            # the Bland call_id so the frontend tracks the correct call.
            # This prevents the "call ended" flash before the phone even rings.
            if record.get("fallback_triggered") and record.get("fallback_call_id"):
                return jsonify({
                    "status":      "initiated",
                    "fallback":    True,
                    "call_id":     record["fallback_call_id"],
                    "call_length": None,
                    "transcript":  [],
                    "raw":         {},
                }), 200

            response = http_requests.get(f"https://api.vapi.ai/call/{call_id}", headers=vapi_headers(), timeout=15)
            raw      = response.json()
            status   = (raw.get("status") or "").lower()
            ended_reason = (raw.get("endedReason") or "").lower()
            is_done  = status in ["ended", "completed"]

            transcript  = parse_vapi_transcript(raw)
            call_length = parse_vapi_duration(raw)

            # Fallback to Bland AI if Vapi/Twilio dropped the call or generated no transcript
            is_failed_vapi = is_done and (
                not transcript or len(transcript) == 0 or
                any(w in ended_reason for w in ["twilio", "fail", "provider", "busy", "no-answer", "error", "closed", "declined"])
            )

            if is_failed_vapi and not record.get("fallback_triggered"):
                phone_num = record.get("phone")
                name_val  = record.get("name", "")
                if phone_num and BLAND_API_KEY:
                    try:
                        greeting_name = f"Namaste {name_val}!" if name_val else "Namaste!"
                        bland_payload = {
                            "phone_number":      phone_num,
                            "task":              TASK.strip(),
                            "first_sentence":    f"{greeting_name} This is Aanya calling from Sunrise Interiors regarding the interior design enquiry you submitted on our website. Is this a good time to chat for a minute?",
                            "voice":             BLAND_VOICE,
                            "language":          "hi",
                            "wait_for_greeting": True,
                            "max_duration":      3,
                            "record":            True
                        }
                        fb_resp = http_requests.post(BLAND_API_URL, json=bland_payload, headers=bland_headers(), timeout=10)

                        if fb_resp.ok:
                            fb_data = fb_resp.json()
                            new_call_id = fb_data.get("call_id")
                            if new_call_id:
                                upsert_record({
                                    "call_id":            call_id,
                                    "fallback_triggered": True,
                                    "fallback_call_id":   new_call_id
                                })
                                upsert_record({
                                    "call_id":      new_call_id,
                                    "provider":     "bland",
                                    "name":         name_val,
                                    "phone":        phone_num,
                                    "initiated_at": datetime.now(timezone.utc).isoformat(),
                                    "status":       "initiated",
                                    "call_length":  None,
                                    "transcript":   [],
                                    "analysis":     None,
                                })
                                return jsonify({
                                    "status":        "initiated",
                                    "fallback":      True,
                                    "call_id":       new_call_id,
                                    "call_length":  None,
                                    "transcript":   [],
                                    "raw":           fb_data
                                }), 200
                    except Exception:
                        pass

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

        except Exception as exc:
            return jsonify({"error": f"Failed to fetch Vapi call: {str(exc)}"}), 500


    else:
        # Bland fallback
        try:
            response = http_requests.get(f"{BLAND_API_URL}/{call_id}", headers=bland_headers(), timeout=15)
            raw = response.json()

            transcript_raw = raw.get("transcripts") or []
            if isinstance(transcript_raw, list):
                transcript = [
                    {"speaker": u.get("user", "unknown"), "text": u.get("text", "")}
                    for u in transcript_raw if u.get("text", "").strip()
                ]
            else:
                transcript = raw.get("concatenated_transcript") or ""

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

            return jsonify({
                "status":      "completed" if is_done else status,
                "call_length": call_length,
                "transcript":  transcript,
                "raw":         raw,
            }), response.status_code

        except Exception as exc:
            return jsonify({"error": f"Failed to reach Bland AI: {str(exc)}"}), 500


@app.route("/api/call/<call_id>/analyze", methods=["POST"])
def analyze_call(call_id):
    """Run post-call NLP analysis and save structured lead details."""
    records = load_history()
    record  = next((r for r in records if r.get("call_id") == call_id), {})
    provider = record.get("provider", TELEPHONY_PROVIDER)

    if provider == "vapi":
        # Extract summary / answers from Vapi transcript
        transcript = record.get("transcript") or []
        full_text  = " ".join([u.get("text", "") for u in transcript]) if isinstance(transcript, list) else str(transcript)

        # High quality fallback extraction for lead summary
        ft = full_text.lower()

        # Detect timeline
        if "today" in ft or "aaj" in ft:
            timeline = "Today"
        elif "tomorrow" in ft or "kal" in ft:
            timeline = "Tomorrow"
        elif "month" in ft:
            timeline = "In 1-2 months"
        elif "week" in ft and "next" in ft:
            timeline = "Next week"
        else:
            timeline = "Next week"

        # Detect time/day preference
        if "today" in ft or "aaj" in ft:
            time_pref = "Today itself"
        elif "tomorrow" in ft or "kal" in ft:
            if "morning" in ft or "subah" in ft:
                time_pref = "Tomorrow morning"
            elif "evening" in ft or "shaam" in ft:
                time_pref = "Tomorrow evening"
            else:
                time_pref = "Tomorrow"
        elif "weekend" in ft:
            if "morning" in ft or "subah" in ft:
                time_pref = "Weekend morning"
            else:
                time_pref = "Weekend evening"
        elif "weekday" in ft or "working day" in ft:
            if "morning" in ft or "subah" in ft:
                time_pref = "Weekday morning"
            else:
                time_pref = "Weekday evening"
        elif "morning" in ft or "subah" in ft:
            time_pref = "Morning"
        elif "evening" in ft or "shaam" in ft:
            time_pref = "Evening"
        else:
            time_pref = "Flexible"

        answers = [
            "Full home interior" if "full" in ft or "home" in ft else "Kitchen / Living room",
            timeline,
            True if any(word in ft for word in ["yes", "sure", "okay", "haan", "theek", "agree"]) else False,
            time_pref,
        ]

        analysis = {
            LEAD_LABELS[i]: answers[i]
            for i in range(min(len(LEAD_LABELS), len(answers)))
        }

        upsert_record({"call_id": call_id, "analysis": analysis})
        return jsonify({"answers": answers, "analysis": analysis}), 200

    else:
        # Bland analysis endpoint
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
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500


# ── Vapi Helper Functions ──────────────────────────────────────────────────────

def parse_vapi_transcript(raw: dict):
    """Extract utterance list or string from Vapi raw response."""
    artifact = raw.get("artifact", {})
    msgs     = artifact.get("messages") or raw.get("messages") or []
    
    transcript = []
    if isinstance(msgs, list):
        for m in msgs:
            role = m.get("role", "")
            text = m.get("message") or m.get("content") or ""
            if role in ["assistant", "user", "human", "bot"] and text.strip():
                speaker = "agent" if role in ["assistant", "bot"] else "user"
                transcript.append({"speaker": speaker, "text": text.strip()})

    if not transcript:
        ct = artifact.get("transcript") or raw.get("transcript") or ""
        if ct:
            return ct

    return transcript


def parse_vapi_duration(raw: dict):
    """Parse duration in seconds from Vapi timestamp fields."""
    try:
        started = raw.get("startedAt")
        ended   = raw.get("endedAt")
        if started and ended:
            d1 = datetime.fromisoformat(started.replace("Z", "+00:00"))
            d2 = datetime.fromisoformat(ended.replace("Z", "+00:00"))
            return (d2 - d1).total_seconds()
    except Exception:
        pass
    return raw.get("duration") or raw.get("costBreakdown", {}).get("duration")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
