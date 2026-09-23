"""
test_ingest.py — Unit tests for scripts/ingest.py

Tests:
  - normalize_appstore_reddit_shape produces correct fields
  - normalize_google_play_scrape skips non-Google-Photos entries
  - normalize_csv skips Candy Crush entries
  - No duplicate IDs in the ingested set
"""

import json
import sys
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

import ingest


class TestNormalizeAppstoreRedditShape:
    def test_extracts_body_as_text(self, tmp_path):
        data = [{"id": "as_001", "body": "Cannot find my old photos", "rating": 1, "url": "http://x.com"}]
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        records = ingest.normalize_appstore_reddit_shape(f)
        assert len(records) == 1
        assert records[0]["text"] == "Cannot find my old photos"
        assert records[0]["source"] == "App Store"
        assert records[0]["rating"] == 1

    def test_skips_empty_body(self, tmp_path):
        data = [
            {"id": "as_001", "body": "", "rating": 5, "url": "http://x.com"},
            {"id": "as_002", "body": "   ", "rating": 5, "url": "http://x.com"},
            {"id": "as_003", "body": "Real review here", "rating": 3, "url": "http://x.com"},
        ]
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        records = ingest.normalize_appstore_reddit_shape(f)
        assert len(records) == 1
        assert records[0]["id"] == "as_003"

    def test_has_required_keys(self, tmp_path):
        data = [{"id": "as_999", "body": "Search is broken", "rating": 2, "url": "http://x.com"}]
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        records = ingest.normalize_appstore_reddit_shape(f)
        for key in ("id", "source", "text", "url", "rating"):
            assert key in records[0], f"Missing key: {key}"


class TestNormalizeGooglePlayScrape:
    def test_skips_candy_crush(self, tmp_path):
        data = [
            # Metadata row
            {"appId": "com.google.android.apps.photos", "score": 4.5, "title": "Google Photos"},
            # Google Photos review
            {"appId": "com.google.android.apps.photos", "userName": "User1", "score": 2,
             "text": "Can't find old photos by location", "date": "2026-01-01", "thumbsUp": 0},
            # Non-Google Photos entry (should be skipped)
            {"appId": "com.king.candycrushsaga", "userName": "User2", "score": 5,
             "text": "Love this candy game", "date": "2026-01-01", "thumbsUp": 0},
        ]
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        records = ingest.normalize_google_play_scrape(f)
        assert len(records) == 1
        assert "candy" not in records[0]["text"].lower()
        assert records[0]["source"] == "Google Play"

    def test_skips_metadata_row(self, tmp_path):
        data = [
            # Metadata: has appId but no userName
            {"appId": "com.google.android.apps.photos", "score": 4.5, "title": "Google Photos", "version": "VARY"},
            {"appId": "com.google.android.apps.photos", "userName": "Alice", "score": 3,
             "text": "Search doesn't find my photos", "date": "2026-01-01", "thumbsUp": 0},
        ]
        f = tmp_path / "test.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        records = ingest.normalize_google_play_scrape(f)
        assert len(records) == 1
        assert records[0]["text"] == "Search doesn't find my photos"


class TestNormalizeCSV:
    def test_skips_candy_crush_entries(self, tmp_path):
        import csv
        rows = [
            {"Source": "Review", "User Quote": "Can't find my old photos, search is broken", "Situation": "", "Problem": "", "What They Remember": "", "What They Don't Remember": "", "Current Workaround": "", "Frequency": "", "Severity": ""},
            {"Source": "Review", "User Quote": "Candy crush boosters are terrible", "Situation": "", "Problem": "", "What They Remember": "", "What They Don't Remember": "", "Current Workaround": "", "Frequency": "", "Severity": ""},
        ]
        f = tmp_path / "test.csv"
        with open(f, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        records = ingest.normalize_csv(f)
        assert len(records) == 1
        assert "candy" not in records[0]["text"].lower()

    def test_empty_quote_skipped(self, tmp_path):
        import csv
        rows = [
            {"Source": "Review", "User Quote": "", "Situation": "", "Problem": "", "What They Remember": "", "What They Don't Remember": "", "Current Workaround": "", "Frequency": "", "Severity": ""},
            {"Source": "Review", "User Quote": "I can't find photos from my vacation", "Situation": "", "Problem": "", "What They Remember": "", "What They Don't Remember": "", "Current Workaround": "", "Frequency": "", "Severity": ""},
        ]
        f = tmp_path / "test.csv"
        with open(f, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        records = ingest.normalize_csv(f)
        assert len(records) == 1


class TestNoDuplicateIDs:
    """Verify ingest_all produces no duplicate IDs across all real files."""
    def test_no_duplicate_ids(self):
        records, _ = ingest.ingest_all()
        ids = [r["id"] for r in records]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {len(ids) - len(set(ids))} duplicates"
