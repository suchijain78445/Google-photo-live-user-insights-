"""
clean.py — Deduplicates records, strips HTML/noise, drops entries under min length.

Input:  data/raw_records.json
Output: data/cleaned.json
"""

import json
import re
import hashlib
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data")
MIN_LENGTH = 30  # characters after cleaning


def strip_html(text: str) -> str:
    """Remove HTML tags."""
    return re.sub(r"<[^>]+>", "", text)


def strip_noise(text: str) -> str:
    """
    Remove:
    - HTML entities (&amp; etc.)
    - Excessive whitespace / newlines
    - Zero-width characters
    - Repeated punctuation (e.g. !!!!!!)
    """
    # HTML entities
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;", "'", text)
    text = re.sub(r"&[a-z]+;", " ", text)

    # Zero-width / invisible chars
    text = re.sub(r"[\u200b\u200c\u200d\ufeff\u00ad]", "", text)

    # Collapse multiple newlines / spaces
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    # Trim
    text = text.strip()
    return text


def normalize_text(text: str) -> str:
    """Normalize text for dedup fingerprinting (lowercase, collapse whitespace)."""
    t = text.lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def text_hash(text: str) -> str:
    return hashlib.md5(normalize_text(text).encode("utf-8")).hexdigest()


def clean_records(records: list[dict]) -> tuple[list[dict], dict]:
    seen_hashes = set()
    cleaned = []
    stats = {
        "input": len(records),
        "dropped_html_strip_empty": 0,
        "dropped_too_short": 0,
        "dropped_duplicate": 0,
        "kept": 0,
    }

    for rec in records:
        # 1. Strip HTML
        text = strip_html(rec["text"])
        # 2. Strip noise
        text = strip_noise(text)

        if not text:
            stats["dropped_html_strip_empty"] += 1
            continue

        # 3. Min length
        if len(text) < MIN_LENGTH:
            stats["dropped_too_short"] += 1
            continue

        # 4. Deduplicate
        h = text_hash(text)
        if h in seen_hashes:
            stats["dropped_duplicate"] += 1
            continue
        seen_hashes.add(h)

        # Produce cleaned record
        cleaned_rec = {**rec, "text": text, "_hash": h}
        cleaned.append(cleaned_rec)
        stats["kept"] += 1

    return cleaned, stats


def main():
    in_path = OUTPUT_DIR / "raw_records.json"
    if not in_path.exists():
        print(f"❌ {in_path} not found. Run ingest.py first.")
        return

    print(f"\n🧹 Cleaning records from {in_path}\n")

    with open(in_path, encoding="utf-8") as f:
        records = json.load(f)

    cleaned, stats = clean_records(records)

    out_path = OUTPUT_DIR / "cleaned.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    print(f"✅ Cleaning complete.")
    print(f"   Input:              {stats['input']}")
    print(f"   Dropped (empty):    {stats['dropped_html_strip_empty']}")
    print(f"   Dropped (too short):{stats['dropped_too_short']}")
    print(f"   Dropped (duplicate):{stats['dropped_duplicate']}")
    print(f"   Kept:               {stats['kept']}")
    print(f"\n   Saved: {out_path}")


if __name__ == "__main__":
    main()
