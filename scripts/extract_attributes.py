"""
extract_attributes.py — (Task 2)
Calls Groq API to extract highly structured attributes from each discovery review.
"""

import json
import os
import time
import httpx
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

def normalize_for_match(text: str) -> str:
    """Normalize text for fuzzy matching — collapse whitespace, lowercase."""
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    return text

def quote_in_corpus(quote_text: str, corpus_text: str) -> bool:
    """Check if quote is a valid substring of the corpus text."""
    if not quote_text:
        return True
    norm_quote = normalize_for_match(quote_text)
    norm_corpus = normalize_for_match(corpus_text)
    return norm_quote in norm_corpus or norm_corpus in norm_quote

def build_prompt(review: dict) -> list[dict]:
    sys_prompt = (
        "You are an expert NLP data extractor for a Google Photos research pipeline. "
        "Your task is to analyze ONE user review and extract precise attributes. "
        "You MUST return ONLY valid JSON matching the strict schema. "
        "Do NOT guess. If something is unknown, use 'unknown' or 'unclear'.\n\n"
        "IMPORTANT for `memory_anchors_missing`: Tag this based on IMPLICIT signals of uncertainty, not just literal keywords like 'forget'.\n"
        "Examples:\n"
        "- \"I have no idea when I took this\" \u2192 exact_date missing\n"
        "- \"not sure where this was\" / \"somewhere in Europe I think\" \u2192 exact_location missing\n"
        "- \"can't remember who all was there\" \u2192 person_present incomplete/missing\n"
        "- \"don't remember what this was for\" \u2192 emotion_or_occasion / activity missing"
    )

    schema = {
      "review_id": review.get("id", ""),
      "source": review.get("source", ""),
      "photo_type": "event | screenshot | document | scanned_old_photo | people | pet | receipt | unknown",
      "memory_anchors_present": ["approx_time", "person_present", "location_description", "emotion_or_occasion", "activity", "device_used"],
      "memory_anchors_missing": ["exact_date", "exact_location", "filename", "album_name"],
      "search_behavior": "reformulated_query | scrolled_manually | used_multiple_apps | gave_up | used_face_filter | used_location_filter | used_natural_language_query | unclear",
      "failure_point": "query_formulation | zero_results | too_many_results | wrong_results | false_positive_category | no_nl_support | unclear",
      "user_segment_signal": "parent | professional | power_user_large_library | casual_small_library | recovering_after_device_change | unclear",
      "verbatim_quote": "MUST EXACTLY MATCH a substring of the text",
      "confidence": 0.0
    }

    user_prompt = f"Review Text:\n{review.get('text', '')}\n\nSchema required:\n{json.dumps(schema, indent=2)}\n\nOnly return JSON. Use empty lists for anchors if none."

    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt}
    ]

def call_groq(messages: list) -> dict | None:
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.1,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

    for attempt in range(3):
        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(GROQ_ENDPOINT, json=payload, headers=headers)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            
            # Clean possible markdown wrapping before parsing json
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            if content.endswith("```"):
                content = content[:-3].strip()

            return json.loads(content)
        except httpx.HTTPStatusError as e:
            print(f" [API Error: {e.response.status_code} - {e.response.text[:200]}] ", end="")
            time.sleep(3)
        except Exception as e:
            print(f" [Error: {e}] ", end="")
            time.sleep(3)
    return None

def main():
    filtered_path = OUTPUT_DIR / "filtered.json"
    extracted_path = OUTPUT_DIR / "extracted.json"
    
    if not filtered_path.exists():
        print(f"ERROR: {filtered_path} not found.")
        return

    with open(filtered_path, encoding="utf-8") as f:
        records = json.load(f)

    print(f"[EXTRACT] Starting extraction on {len(records)} records...")
    
    results = []
    for i, rec in enumerate(records):
        print(f"  Extracting {i+1}/{len(records)}...", end="", flush=True)
        messages = build_prompt(rec)
        extracted = call_groq(messages)
        
        if not extracted:
            print(" FAILED (LLM error)")
            continue
            
        # Ensure review_id and source match
        extracted["review_id"] = rec.get("id", f"rev_{i}")
        extracted["source"] = rec.get("source", "unknown")
        
        # Zero-hallucination validation
        quote = extracted.get("verbatim_quote", "")
        if not quote_in_corpus(quote, rec.get("text", "")):
            print(" FAILED (Hallucinated quote)")
            # Fix hallucination by dropping quote
            extracted["verbatim_quote"] = ""
        else:
            print(" OK")
            
        results.append(extracted)
        
        # Rate limiting prevention
        time.sleep(0.5)

    with open(extracted_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n[EXTRACT] Saved {len(results)} structured records to {extracted_path}")

if __name__ == "__main__":
    main()
