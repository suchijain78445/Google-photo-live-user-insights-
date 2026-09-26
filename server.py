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

EXTRACTED_RECORDS = []

def load_corpus() -> tuple[str, list[str]]:
    """Load structured data for RAG (Task 8)."""
    global EXTRACTED_RECORDS
    extracted_path = DATA_DIR / "extracted.json"
    answers_path = DATA_DIR / "core_answers.json"
    
    if not extracted_path.exists():
        return "No extracted data.", []
        
    with open(extracted_path, encoding="utf-8-sig") as f:
        EXTRACTED_RECORDS = json.load(f)
        extracted = EXTRACTED_RECORDS
        
    with open(answers_path, encoding="utf-8-sig") as f:
        answers = json.load(f)

    # Build structured text
    lines = []
    sources = []
    
    lines.append(f"TOTAL REVIEWS ANALYZED: {answers.get('total_records', 0)}")
    lines.append("AGGREGATED STATISTICS (Core Answers):")
    lines.append(json.dumps(answers, indent=2)[:5000]) # Cap to avoid huge prompt
    
    lines.append("\n\nDETAILED REVIEW EVIDENCE (Sample of structured records):")
    total = sum(len(line) for line in lines)
    for rec in extracted:
        sources.append(rec.get("source", ""))
        rec_str = json.dumps(rec, indent=2)
        if total + len(rec_str) > 20_000:
            break
        lines.append(rec_str)
        total += len(rec_str)
        
    return "\n".join(lines), sources

CORPUS_TEXT, CORPUS_SOURCES = load_corpus()
print(f"[SERVER] Structured RAG data loaded: {len(CORPUS_TEXT):,} chars from {len(set(CORPUS_SOURCES))} sources")


# ── System prompt ─────────────────────────────────────────────
SYSTEM_PROMPT = (
    "You are a senior UX researcher and product strategist specializing in photo management "
    "and memory retrieval. You analyze structured JSON data derived from real Google Photos user reviews.\n\n"
    "Rules:\n"
    "1. Only cite verbatim quotes that actually appear in the 'verbatim_quote' fields provided.\n"
    "2. Base your statistical claims ONLY on the AGGREGATED STATISTICS provided.\n"
    "3. Return ONLY valid JSON — no markdown fences, no extra text.\n"
    "4. Include exactly 5 key_findings.\n"
    "5. Include 2-4 representative_quotes, copied exactly from the structured records.\n"
    "6. CRITICAL: If there is 0 evidence or 0 relevant quotes in the provided data for the specific question, you MUST return confidence_score: 0.\n"
)


def build_user_prompt(question: str) -> str:
    sources_str = ", ".join(sorted(set(CORPUS_SOURCES)))
    return f"""Research question: {question}

Data Context (Aggregated stats + Sample of structured records):
{CORPUS_TEXT}

Sources in dataset: {sources_str}

Return ONLY this JSON object — no markdown, no explanation:
{{
  "question": "{question}",
  "executive_summary": "2-3 sentence summary answering the question",
  "key_findings": [
    "Finding 1 — include a count where possible, e.g. 'Over 20 reviews mention...'",
    "Finding 2",
    "Finding 3",
    "Finding 4",
    "Finding 5"
  ],
  "representative_quotes": [
    {{"text": "verbatim quote copied exactly from a verbatim_quote field above", "source": "Google Play|App Store|Reddit|Forums/Community", "rating": null}},
    {{"text": "another verbatim quote", "source": "...", "rating": 1}}
  ],
  "pm_insight": "1-3 sentences on the product/engineering opportunity",
  "confidence_score": 0,
  "confidence_label": "High|Medium|Low",
  "confidence_reason": "short phrase e.g. based on structured data frequencies",
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

def check_evidence_gate(question: str) -> bool:
    """Return True if there is evidence, False if we should skip LLM."""
    query_lower = question.lower()
    
    # 1. Map question keywords to expected relevant fields
    target_field = None
    if "forget" in query_lower or "remember" in query_lower or "memory" in query_lower:
        target_field = "memory_anchors_missing"
    elif "search" in query_lower or "find" in query_lower or "query" in query_lower:
        target_field = "search_behavior"
    elif "type" in query_lower or "kind of photo" in query_lower:
        target_field = "photo_type"
    elif "fail" in query_lower or "wrong" in query_lower:
        target_field = "failure_point"
    
    if not target_field:
        return True # If no specific field, let LLM decide
        
    # 2. Count records where the target field is non-null/non-empty
    count = 0
    for rec in EXTRACTED_RECORDS:
        val = rec.get(target_field)
        # Check if list is not empty, or string is valid
        if isinstance(val, list) and len(val) > 0 and val[0] != "unknown":
            count += 1
        elif isinstance(val, str) and val and val != "unknown" and val != "unclear":
            count += 1
            
    return count > 0

# ── Routes ────────────────────────────────────────────────────

@app.route("/api/findings")
def api_findings():
    return send_file(DATA_DIR / "findings.json")

@app.route("/api/core-answers")
def api_core_answers():
    return send_file(DATA_DIR / "core_answers.json")

@app.route("/api/sample-questions")
def api_sample_questions():
    return send_file(DATA_DIR / "sample_questions.json")

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

    # Hard Evidence Gate
    if not check_evidence_gate(question):
        print(f"[/api/ask] Evidence gate failed for question: {question}")
        return jsonify({
            "question": question,
            "executive_summary": "No direct evidence was found in the current dataset for this question. This likely reflects a gap in what the extraction pipeline captured, not a confirmed absence of the underlying user behavior.",
            "key_findings": [],
            "pm_insight": "Recommend expanding extraction coverage or re-querying with related phrasing before treating this as a validated finding.",
            "confidence_score": 0,
            "confidence_label": "Low",
            "confidence_reason": "Zero matching extracted records",
            "representative_quotes": [],
            "sources": []
        })

    try:
        finding = call_groq(question)
        if finding.get("confidence_score", 100) == 0:
            print(f"[/api/ask] LLM returned confidence 0, returning fallback.")
            return jsonify({
                "question": question,
                "executive_summary": "No direct evidence was found in the current dataset for this question. This likely reflects a gap in what the extraction pipeline captured, not a confirmed absence of the underlying user behavior.",
                "key_findings": [],
                "pm_insight": "Recommend expanding extraction coverage or re-querying with related phrasing before treating this as a validated finding.",
                "confidence_score": 0,
                "confidence_label": "Low",
                "confidence_reason": "Zero matching extracted records",
                "representative_quotes": [],
                "sources": []
            })
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
