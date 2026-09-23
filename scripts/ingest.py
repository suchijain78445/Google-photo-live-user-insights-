"""
ingest.py — Reads all files in 'Data reviews/', normalizes each entry into:
    {id, source, text, url, rating}

Source files and their schemas:
  1. appstore_reviews_reddit_shape.json  → body, rating, url (Google Photos App Store)
  2. combined_all_matching_reviews 2.json → body, url (Google Photos Community Forums)
  3. curated_matching_pain_points 1.json  → body, url (Curated Forums/Community)
  4. dataset_app-store-reviews-scraper_*.json → text, score, url (raw scrape — Candy Crush, SKIP)
  5. dataset_google-play-scraper_*.json   → text, score, appId (Google Play)
  6. Google Photos – User Research Dataset - Sheet1.csv → User Quote column (Research CSV)
"""

import json
import csv
import os
import glob
import hashlib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "Data reviews")
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data")
OUTPUT_DIR.mkdir(exist_ok=True)

# Google Photos App Store ID (itunes)
GOOGLE_PHOTOS_APPSTORE_ID = "962194608"
# Google Photos Play Store appId
GOOGLE_PHOTOS_PLAY_ID = "com.google.android.apps.photos"


def make_id(source_tag: str, raw_id: str) -> str:
    """Generate a stable unique ID."""
    return f"{source_tag}_{raw_id}"


def normalize_appstore_reddit_shape(path: Path) -> list[dict]:
    """
    Schema: [{id, body, url, rating, communityName, parsedCommunityName, ...}]
    Source label: App Store
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for entry in data:
        text = (entry.get("body") or "").strip()
        if not text:
            continue
        records.append({
            "id": entry.get("id", make_id("as_rs", hashlib.md5(text.encode()).hexdigest()[:8])),
            "source": "App Store",
            "text": text,
            "url": entry.get("url", ""),
            "rating": entry.get("rating"),
        })
    return records


def normalize_combined_json(path: Path, source_label: str) -> list[dict]:
    """
    Schema: [{id, body, url, communityName, parsedCommunityName, ...}]
    Used for both combined_all_matching_reviews and curated_matching_pain_points.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for entry in data:
        text = (entry.get("body") or "").strip()
        if not text:
            continue
        # Infer source from communityName
        community = entry.get("communityName", "").lower()
        if "reddit" in community:
            src = "Reddit"
        elif "community" in community or "google photos" in community:
            src = "Forums/Community"
        elif "app store" in community:
            src = "App Store"
        else:
            src = source_label

        records.append({
            "id": entry.get("id", make_id("comb", hashlib.md5(text.encode()).hexdigest()[:8])),
            "source": src,
            "text": text,
            "url": entry.get("url", ""),
            "rating": entry.get("rating"),
        })
    return records


def normalize_raw_appstore_scrape(path: Path) -> list[dict]:
    """
    Schema: [{id, text, score, url, userName, version, ...}]
    Only includes entries where url contains the Google Photos app ID.
    Most entries in this file are Candy Crush — those are skipped.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for entry in data:
        url = entry.get("url", "")
        # Only include if this is a Google Photos review
        if GOOGLE_PHOTOS_APPSTORE_ID not in url:
            continue
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        records.append({
            "id": make_id("as_raw", str(entry.get("id", ""))),
            "source": "App Store",
            "text": text,
            "url": url,
            "rating": entry.get("score"),
        })
    return records


def normalize_google_play_scrape(path: Path) -> list[dict]:
    """
    Schema: [{appId, text, score, date, userName, version, replyText, ...}]
    First entry is app metadata (no userName) — skip it.
    Only includes entries where appId == GOOGLE_PHOTOS_PLAY_ID.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for i, entry in enumerate(data):
        app_id = entry.get("appId", "")
        if app_id != GOOGLE_PHOTOS_PLAY_ID:
            continue
        # Skip metadata row (first entry, no userName, no text)
        if not entry.get("userName"):
            continue
        text = (entry.get("text") or "").strip()
        if not text:
            continue
        records.append({
            "id": make_id("gp", f"{i}_{hashlib.md5(text.encode()).hexdigest()[:6]}"),
            "source": "Google Play",
            "text": text,
            "url": f"https://play.google.com/store/apps/details?id={GOOGLE_PHOTOS_PLAY_ID}",
            "rating": entry.get("score"),
        })
    return records


def normalize_csv(path: Path) -> list[dict]:
    """
    Schema: CSV with columns: Source, User Quote, Situation, Problem,
            What They Remember, What They Don't Remember, Current Workaround,
            Frequency, Severity
    The 'User Quote' column is the primary text.
    Source column maps to our source labels.
    """
    SOURCE_MAP = {
        "review": "App Store",
        "reddit": "Reddit",
        "forum": "Forums/Community",
        "community": "Forums/Community",
        "google play": "Google Play",
        "app store": "App Store",
        "play store": "Google Play",
    }

    records = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            text = (row.get("User Quote") or "").strip()
            if not text:
                continue

            raw_source = (row.get("Source") or "").strip().lower()
            src = SOURCE_MAP.get(raw_source, "Research Dataset")

            # Skip obvious non-Google-Photos entries (Candy Crush, etc.)
            # These are in the CSV because the raw scraper data was included
            candy_crush_markers = [
                "candy", "booster", "game", "level", "lives", "coins",
                "match", "crush", "arcade", "puzzle game"
            ]
            text_lower = text.lower()
            if any(marker in text_lower for marker in candy_crush_markers):
                continue

            records.append({
                "id": make_id("csv", str(i)),
                "source": src,
                "text": text,
                "url": "",
                "rating": None,
                "situation": (row.get("Situation") or "").strip() or None,
                "problem": (row.get("Problem") or "").strip() or None,
                "what_they_remember": (row.get("What They Remember") or "").strip() or None,
                "what_they_dont_remember": (row.get("What They Don't Remember") or "").strip() or None,
                "workaround": (row.get("Current Workaround") or "").strip() or None,
                "frequency": (row.get("Frequency") or "").strip() or None,
                "severity": (row.get("Severity") or "").strip() or None,
            })
    return records


def ingest_all() -> list[dict]:
    """Read all files in DATA_DIR and return a unified list of records."""
    all_records = []
    stats = {}

    for path in sorted(DATA_DIR.iterdir()):
        name = path.name
        if path.suffix == ".json":
            if "reddit_shape" in name:
                records = normalize_appstore_reddit_shape(path)
                label = "App Store (Reddit-shape)"
            elif "combined_all_matching" in name:
                records = normalize_combined_json(path, "Forums/Community")
                label = "Combined Reviews (Community)"
            elif "curated_matching" in name:
                records = normalize_combined_json(path, "Forums/Community")
                label = "Curated Pain Points (Community)"
            elif "app-store-reviews-scraper" in name:
                records = normalize_raw_appstore_scrape(path)
                label = "Raw App Store Scrape (filtered)"
            elif "google-play-scraper" in name:
                records = normalize_google_play_scrape(path)
                label = "Google Play Scrape"
            else:
                print(f"  [SKIP] Unknown JSON file: {name}")
                continue

        elif path.suffix == ".csv":
            records = normalize_csv(path)
            label = "Research Dataset CSV"
        else:
            print(f"  [SKIP] Unsupported file type: {name}")
            continue

        print(f"  [OK]  {label}: {len(records)} records")
        stats[label] = len(records)
        all_records.extend(records)

    return all_records, stats


def main():
    print(f"\n[INGEST] Data dir: {DATA_DIR}\n")
    records, stats = ingest_all()

    # Save raw count summary
    summary = {
        "total": len(records),
        "by_source_file": stats,
        "by_source_label": {},
    }
    for r in records:
        src = r["source"]
        summary["by_source_label"][src] = summary["by_source_label"].get(src, 0) + 1

    out_path = OUTPUT_DIR / "raw_count.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Save all raw normalized records
    records_path = OUTPUT_DIR / "raw_records.json"
    with open(records_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Ingestion complete.")
    print(f"   Total records: {len(records)}")
    print(f"   By source:")
    for src, cnt in summary["by_source_label"].items():
        print(f"     {src}: {cnt}")
    print(f"\n   Saved: {out_path}")
    print(f"   Saved: {records_path}")


if __name__ == "__main__":
    main()
