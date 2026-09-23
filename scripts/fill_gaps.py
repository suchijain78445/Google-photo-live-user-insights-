"""
fill_gaps.py — Re-generates only the failed/empty findings from findings.json.
               Reads current findings.json, identifies empty placeholders, and
               retries those questions with longer timeouts and improved JSON repair.

Usage:
    python scripts/fill_gaps.py
"""

import json
import os
import re
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR   = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data")

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL    = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "You are a senior UX researcher analyzing Google Photos user reviews. "
    "Return ONLY a valid, complete JSON object — no markdown fences, no extra text. "
    "Ensure all strings are properly closed with double-quotes. "
    "Do not truncate your response."
)


def load_corpus():
    filtered_path = OUTPUT_DIR / "filtered.json"
    with open(filtered_path, encoding="utf-8") as f:
        records = json.load(f)
    lines, sources = [], []
    total = 0
    for rec in records:
        src = rec.get("source", "")
        rating = rec.get("rating")
        text = rec.get("text", "")
        rating_str = f" [★{rating}]" if rating else ""
        line = f'[{src}{rating_str}]: "{text}"'
        if total + len(line) > 60_000:
            break
        lines.append(line)
        sources.append(src)
        total += len(line)
    return "\n".join(lines), sources


def build_prompt(question: str, corpus: str, sources: list) -> str:
    sources_str = ", ".join(sorted(set(sources)))
    return f"""Research question: {question}

User review corpus:
{corpus}

Sources: {sources_str}

Return ONLY this JSON — no markdown, no explanation, no truncation:
{{
  "question": "{question}",
  "executive_summary": "2-3 sentence summary",
  "key_findings": ["Finding 1 with count", "Finding 2", "Finding 3", "Finding 4", "Finding 5"],
  "representative_quotes": [
    {{"text": "verbatim quote from corpus", "source": "App Store|Google Play|Forums/Community", "rating": null}}
  ],
  "pm_insight": "1-3 sentences on the product opportunity",
  "confidence_score": 60,
  "confidence_label": "Medium",
  "confidence_reason": "based on corpus evidence",
  "sources": ["source names that contributed"]
}}"""


def try_fix_json(raw: str) -> dict | None:
    """Attempt to recover a truncated JSON string."""
    raw = raw.strip()

    # Strip fences
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()

    # Try as-is first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try closing unclosed strings/brackets
    # Count open braces
    open_braces  = raw.count('{') - raw.count('}')
    open_brackets = raw.count('[') - raw.count(']')

    fixed = raw
    # Close any open string (look for odd number of unescaped quotes)
    # Simple heuristic: if last char isn't } or ], try to close
    if not fixed.rstrip().endswith('}'):
        # Close open arrays
        fixed = fixed.rstrip().rstrip(',')
        fixed += ']' * open_brackets
        fixed += '}' * open_braces

    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Last resort: extract fields we can salvage
    return None


def call_groq(question: str, corpus: str, sources: list) -> dict | None:
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_prompt(question, corpus, sources)},
        ],
        "max_tokens": 2048,
        "temperature": 0.2,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "User-Agent": "Mozilla/5.0 (compatible; RecallResearchBot/1.0)",
    }

    for attempt in range(4):
        try:
            with httpx.Client(timeout=90) as client:
                resp = client.post(GROQ_ENDPOINT, json=payload, headers=headers)

            if resp.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"    [RATE LIMIT] waiting {wait}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            print(f"    Raw length: {len(content)} chars")

            result = try_fix_json(content)
            if result:
                return result

            print(f"    [WARN] JSON parse failed attempt {attempt + 1}")
            time.sleep(5)

        except httpx.HTTPStatusError as e:
            print(f"    [ERROR] HTTP {e.response.status_code}: {e.response.text[:150]}")
            time.sleep(10)
        except Exception as e:
            print(f"    [ERROR] {e}")
            time.sleep(5)

    return None


def main():
    findings_path = OUTPUT_DIR / "findings.json"
    if not findings_path.exists():
        print("ERROR: data/findings.json not found. Run summarize.py first.")
        return

    with open(findings_path, encoding="utf-8") as f:
        findings = json.load(f)

    corpus_text, all_sources = load_corpus()

    # Find failed findings (empty key_findings = placeholder)
    failed_indices = [
        i for i, f in enumerate(findings)
        if not f.get("key_findings")
    ]

    if not failed_indices:
        print("All findings are already complete!")
        return

    print(f"\n[FILL GAPS] Model: {GROQ_MODEL}")
    print(f"[FILL GAPS] Re-generating {len(failed_indices)} failed findings\n")

    for i in failed_indices:
        question = findings[i]["question"]
        print(f"  [{i+1:02d}/14] {question[:70]}...")
        result = call_groq(question, corpus_text, all_sources)

        if result:
            result["question"] = question
            findings[i] = result
            score = result.get("confidence_score", 0)
            label = result.get("confidence_label", "?")
            print(f"         ✓  confidence={score}% ({label})")
        else:
            print(f"         ✗  STILL FAILED — keeping placeholder")

        time.sleep(3)  # gentle delay

    # Save both locations
    with open(findings_path, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2, ensure_ascii=False)

    dashboard_path = BASE_DIR / "dashboard" / "findings.json"
    with open(dashboard_path, "w", encoding="utf-8") as f:
        json.dump(findings, f, indent=2, ensure_ascii=False)

    success = len([f for f in findings if f.get("key_findings")])
    print(f"\n[DONE] {success}/14 findings now complete")
    print(f"       Saved -> {findings_path}")
    print(f"       Saved -> {dashboard_path}")
    print(f"\n       Refresh http://localhost:5000 to see all findings!")


if __name__ == "__main__":
    main()
