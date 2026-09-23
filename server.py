"""
server.py — Local Flask server for Recall dashboard.

Does two things:
  1. Serves dashboard/ as static files at http://localhost:5000/
  2. Exposes POST /api/ask — a secure proxy to Groq API that keeps
     GROQ_API_KEY on the server side, never in the browser.

Usage:
    python server.py

Then open: http://localhost:5000
"""

import json
import os
import sys
import httpx
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

BASE_DIR   = Path(__file__).parent
DASHBOARD  = BASE_DIR / "dashboard"
DATA_DIR   = BASE_DIR / os.getenv("OUTPUT_DIR", "data")

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL    = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

app = Flask(__name__, static_folder=str(DASHBOARD))
CORS(app)  # Allow requests from same origin (dashboard JS → /api/ask)

# ── Validate key on startup ───────────────────────────────────
if not GROQ_API_KEY:
    print("[ERROR] GROQ_API_KEY not set in .env — /api/ask will not work.")

# ── Load filtered corpus once at startup ─────────────────────
def load_corpus() -> tuple[str, list[str]]:
    """Load filtered.json and build corpus text + source list."""
    filtered_path = DATA_DIR / "filtered.json"
    if not filtered_path.exists():
        return "", []
    with open(filtered_path, encoding="utf-8") as f:
        records = json.load(f)
    lines, sources = [], []
    total = 0
    for rec in records:
        src  = rec.get("source", "")
        rating = rec.get("rating")
        text = rec.get("text", "")
        rating_str = f" [★{rating}]" if rating else ""
        line = f'[{src}{rating_str}]: "{text}"'
        if total + len(line) > 70_000:
            break
        lines.append(line)
        sources.append(src)
        total += len(line)
    return "\n".join(lines), sources

CORPUS_TEXT, CORPUS_SOURCES = load_corpus()
print(f"[SERVER] Corpus loaded: {len(CORPUS_TEXT):,} chars from {len(set(CORPUS_SOURCES))} sources")


# ── System prompt ─────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are a senior UX researcher and product strategist specializing in photo management "
    "and memory retrieval. You analyze real Google Photos user reviews.\n\n"
    "Rules:\n"
    "1. Only cite verbatim quotes that actually appear in the corpus provided.\n"
    "2. Return ONLY valid JSON — no markdown fences, no extra text.\n"
    "3. Set confidence_score <= 70 unless at least 2 independent sources support the finding.\n"
    "4. Include 2-4 representative_quotes, copied verbatim from the corpus.\n"
    "5. key_findings must have exactly 5 items."
)


def build_user_prompt(question: str) -> str:
    sources_str = ", ".join(sorted(set(CORPUS_SOURCES)))
    return f"""Research question: {question}

User review corpus (real verbatim quotes from Google Photos users):
{CORPUS_TEXT}

Sources in dataset: {sources_str}

Return ONLY this JSON object — no markdown, no explanation:
{{
  "question": "{question}",
  "executive_summary": "2-3 sentence summary of the main finding",
  "key_findings": [
    "Finding 1 — include a count where possible, e.g. 'Over 20 reviews mention...'",
    "Finding 2",
    "Finding 3",
    "Finding 4",
    "Finding 5"
  ],
  "representative_quotes": [
    {{"text": "verbatim quote copied exactly from corpus above", "source": "Google Play|App Store|Reddit|Forums/Community", "rating": null}},
    {{"text": "another verbatim quote", "source": "...", "rating": 1}}
  ],
  "pm_insight": "1-3 sentences on the product/engineering opportunity",
  "confidence_score": 0,
  "confidence_label": "High|Medium|Low",
  "confidence_reason": "short phrase e.g. based on review volume and cross-source consistency",
  "sources": ["only sources that contributed evidence"]
}}"""


def call_groq(question: str) -> dict:
    """Call Groq API via httpx (server-side, key never leaves server)."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_user_prompt(question)},
        ],
        "max_tokens": 2048,
        "temperature": 0.3,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {groq_key}",
        "User-Agent": "Mozilla/5.0 (compatible; RecallResearchBot/1.0)",
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(GROQ_ENDPOINT, json=payload, headers=headers)

    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if model adds them
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    if content.endswith("```"):
        content = content[:-3].strip()

    finding = json.loads(content)
    finding["question"] = question
    return finding


# ── Routes ────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the dashboard index.html."""
    return send_file(DASHBOARD / "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    """Serve all other dashboard assets (CSS, JS, findings.json)."""
    return send_from_directory(DASHBOARD, filename)


@app.route("/api/ask", methods=["POST"])
@app.route("/api/index.py", methods=["POST"])
def api_ask():
    """
    Secure proxy endpoint for the Ask AI feature.
    Body: { "question": "..." }
    Returns: finding object in the standard schema.
    """
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        return jsonify({"error": "GROQ_API_KEY not configured on server"}), 503

    body = request.get_json(force=True, silent=True) or {}
    question = (body.get("question") or "").strip()

    if not question:
        return jsonify({"error": "Missing 'question' field in request body"}), 400

    if len(question) > 500:
        return jsonify({"error": "Question too long (max 500 chars)"}), 400

    print(f"[/api/ask] question='{question[:80]}'")

    try:
        finding = call_groq(question)
        return jsonify(finding)
    except httpx.HTTPStatusError as e:
        body_text = e.response.text
        print(f"[/api/ask] Groq HTTP error {e.response.status_code}: {body_text[:200]}")
        return jsonify({"error": f"Groq API error {e.response.status_code}: {body_text[:200]}"}), 502
    except json.JSONDecodeError as e:
        print(f"[/api/ask] JSON parse error: {e}")
        return jsonify({"error": f"Model returned invalid JSON: {e}"}), 502
    except Exception as e:
        print(f"[/api/ask] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    """Health check — confirms server + corpus are ready."""
    return jsonify({
        "status": "ok",
        "model": GROQ_MODEL,
        "corpus_chars": len(CORPUS_TEXT),
        "corpus_sources": sorted(set(CORPUS_SOURCES)),
        "groq_key_set": bool(GROQ_API_KEY),
    })


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n{'='*55}")
    print(f"  Recall Dashboard Server")
    print(f"  http://localhost:{port}")
    print(f"  API proxy: POST http://localhost:{port}/api/ask")
    print(f"  Model: {GROQ_MODEL}")
    print(f"  Corpus: {len(CORPUS_TEXT):,} chars")
    print(f"{'='*55}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
