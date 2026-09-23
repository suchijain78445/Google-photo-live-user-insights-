"""
summarize.py — Calls Groq API (Llama 3.3 70B, OpenAI-compatible endpoint) to generate
               structured findings for 14 research questions.

Output schema per finding:
{
  "question": "...",
  "executive_summary": "2-3 sentences",
  "key_findings": ["finding 1 (include a review count or fraction where possible)", ...x5],
  "representative_quotes": [{"text": "verbatim quote", "source": "...", "rating": number|null}],
  "pm_insight": "1-3 sentences",
  "confidence_score": 0-100,
  "confidence_label": "High"|"Medium"|"Low",
  "confidence_reason": "short phrase",
  "sources": ["Google Play Reviews", ...]
}

Input:  data/filtered.json
Output: data/findings.json + dashboard/findings.json
"""

import json
import os
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

RESEARCH_QUESTIONS = [
    "What kinds of old photos do users struggle to retrieve?",
    "What information do people actually remember about a photo?",
    "What information have they forgotten when trying to find a photo?",
    "How do users formulate searches when their memory is incomplete?",
    "What features do users request most for finding old photos?",
    "How do face and people recognition features affect photo retrieval?",
    "Which retrieval problem is the most severe — search failure, memory gaps, or feature regressions?",
    "How does location-based search fail users, and what would fix it?",
    "Which user segments are more likely to experiment with alternative search methods?",
    "What unmet needs emerge consistently across all discussions?",
    "How do screenshots and document photos create a unique retrieval problem compared to regular photos?",
    "How does the mismatch between what users remember (context/purpose) and what the system expects (date/object/person) cause retrieval failure?",
    "What workarounds do users adopt when Google Photos search fails them, and how effective are these workarounds?",
    "How does excessive scrolling through large photo libraries affect user experience and what triggers users to give up searching?",
]


def build_system_prompt() -> str:
    return (
        "You are a senior UX researcher and product strategist specializing in photo management and memory retrieval. "
        "Your task is to analyze real user reviews, forum posts, and app store feedback about Google Photos to answer specific research questions.\n\n"
        "You MUST:\n"
        "1. Only cite verbatim quotes that actually appear in the provided user reviews corpus.\n"
        "2. Count mentions accurately — if you say 'X reviews mention', it must be a real estimate from the data.\n"
        "3. Return ONLY valid JSON matching the exact schema provided. No markdown fences, no extra text.\n"
        "4. Set confidence_score <= 70 unless at least 2 independent sources support the finding.\n"
        "5. Include 2-4 representative quotes per finding, drawn verbatim from the corpus.\n"
        "6. The sources list should only include sources that actually contributed evidence."
    )


def build_user_prompt(question: str, corpus_sample: str, all_sources: list) -> str:
    sources_str = ", ".join(sorted(set(all_sources)))
    return f"""Research question: {question}

User review corpus (analyze ALL text below for patterns):
{corpus_sample}

Sources present in dataset: {sources_str}

Return a JSON object with EXACTLY this schema — no markdown, no extra text, just the JSON:
{{
  "question": "{question}",
  "executive_summary": "2-3 sentence summary of the main finding",
  "key_findings": [
    "Finding 1 — include a review count or fraction where possible, e.g. 'Over 20 reviews mention...'",
    "Finding 2",
    "Finding 3",
    "Finding 4",
    "Finding 5"
  ],
  "representative_quotes": [
    {{"text": "verbatim quote copied exactly from corpus", "source": "Google Play|App Store|Reddit|Forums/Community", "rating": null}},
    {{"text": "another verbatim quote", "source": "...", "rating": 1}}
  ],
  "pm_insight": "1-3 sentences framing the product/engineering opportunity implied by this finding",
  "confidence_score": 0,
  "confidence_label": "High|Medium|Low",
  "confidence_reason": "short phrase e.g. 'based on review volume and cross-source consistency'",
  "sources": ["list only sources that contributed evidence"]
}}

Rules:
- key_findings must have exactly 5 items
- representative_quotes must have 2-4 items copied verbatim from the corpus above
- confidence_score must be an integer 0-100, and <= 70 if fewer than 2 independent sources
- High = 75-100, Medium = 45-74, Low = 0-44
- Return ONLY the JSON object — no markdown, no extra explanation"""


def prepare_corpus(filtered_records: list, max_chars: int = 70000) -> tuple:
    lines = []
    sources = []
    total = 0
    for rec in filtered_records:
        src = rec["source"]
        rating = rec.get("rating")
        text = rec["text"]
        rating_str = f" [★{rating}]" if rating else ""
        line = f'[{src}{rating_str}]: "{text}"'
        if total + len(line) > max_chars:
            break
        lines.append(line)
        sources.append(src)
        total += len(line)
    return "\n".join(lines), sources


def call_groq(question: str, corpus: str, sources: list) -> dict | None:
    """Call Groq API via httpx and return parsed JSON finding."""
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user",   "content": build_user_prompt(question, corpus, sources)},
        ],
        "max_tokens": 2048,
        "temperature": 0.3,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "User-Agent": "Mozilla/5.0 (compatible; RecallResearchBot/1.0)",
    }

    for attempt in range(3):
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(GROQ_ENDPOINT, json=payload, headers=headers)

            if resp.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"    [WARN] Rate limited — waiting {wait}s...")
                time.sleep(wait)
                continue

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

            return json.loads(content)

        except json.JSONDecodeError as e:
            print(f"    [WARN] JSON parse error attempt {attempt + 1}: {e}")
            time.sleep(3)
        except httpx.HTTPStatusError as e:
            print(f"    [ERROR] HTTP {e.response.status_code}: {e.response.text[:200]}")
            time.sleep(5)
        except Exception as e:
            print(f"    [ERROR] {e}")
            time.sleep(5)

    return None


def main():
    filtered_path = OUTPUT_DIR / "filtered.json"
    if not filtered_path.exists():
        print(f"ERROR: {filtered_path} not found. Run filter_discovery.py first.")
        return

    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        print("ERROR: GROQ_API_KEY not set in .env")
        return

    print(f"\n[SUMMARIZE] Model: {GROQ_MODEL}")
    print(f"[SUMMARIZE] Endpoint: {GROQ_ENDPOINT}\n")

    with open(filtered_path, encoding="utf-8") as f:
        filtered_records = json.load(f)

    corpus_text, all_sources = prepare_corpus(filtered_records)
    print(f"   Corpus: {len(filtered_records)} records, {len(corpus_text):,} chars")
    print(f"   Sources: {sorted(set(all_sources))}\n")

    findings = []
    total = len(RESEARCH_QUESTIONS)

    for i, question in enumerate(RESEARCH_QUESTIONS, 1):
        print(f"  [{i:02d}/{total}] {question[:75]}...")
        finding = call_groq(question, corpus_text, all_sources)

        if finding:
            finding["question"] = question  # Ensure exact match
            findings.append(finding)
            score = finding.get("confidence_score", 0)
            label = finding.get("confidence_label", "?")
            print(f"          OK  confidence={score}% ({label})")
        else:
            print(f"          FAIL — using empty placeholder")
            findings.append({
                "question": question,
                "executive_summary": "Finding could not be generated.",
                "key_findings": [],
                "representative_quotes": [],
                "pm_insight": "",
                "confidence_score": 0,
                "confidence_label": "Low",
                "confidence_reason": "API call failed",
                "sources": [],
            })

        # Small buffer between calls to respect rate limits
        time.sleep(1.2)

    # Save to data/
    out_path = OUTPUT_DIR / "findings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2, ensure_ascii=False)

    # Copy to dashboard/
    dashboard_dir = BASE_DIR / "dashboard"
    dashboard_dir.mkdir(exist_ok=True)
    dash_path = dashboard_dir / "findings.json"
    with open(dash_path, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2, ensure_ascii=False)

    success = len([f for f in findings if f.get("key_findings")])
    print(f"\n[DONE] {success}/{total} findings generated")
    print(f"       Saved -> {out_path}")
    print(f"       Saved -> {dash_path}")


if __name__ == "__main__":
    main()
