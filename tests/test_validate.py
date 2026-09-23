"""
test_validate.py — Unit tests for scripts/validate.py

Tests:
  - No duplicate quotes across findings
  - Every finding has at least one real quote
  - confidence_score ≤ 70 if fewer than 2 sources
  - Schema fields all present
  - Verbatim quote detection logic
"""

import json
import sys
import pytest
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

import validate


CORPUS_SET = {
    "i can't find my old photos using the search",
    "search doesn't work for face recognition it misses half the photos",
    "i scrolled for hours trying to find a prescription screenshot",
    "the location search never shows my trip photos from italy",
    "i remember taking the photo but google photos can't find it",
}

VALID_FINDING = {
    "question": "What kinds of old photos do users struggle to retrieve?",
    "executive_summary": "Users consistently report struggling to find old screenshots and trip photos.",
    "key_findings": [
        "Finding 1: Many users mention screenshot retrieval failures.",
        "Finding 2: Trip/vacation photo retrieval is difficult.",
        "Finding 3: Prescription and document photos are hard to locate.",
        "Finding 4: Face search misses many photos.",
        "Finding 5: Location search fails for international trips.",
    ],
    "representative_quotes": [
        {"text": "i scrolled for hours trying to find a prescription screenshot", "source": "Google Play", "rating": 1},
        {"text": "the location search never shows my trip photos from italy", "source": "Forums/Community", "rating": None},
    ],
    "pm_insight": "A context-based search mode would address the core pain point.",
    "confidence_score": 65,
    "confidence_label": "Medium",
    "confidence_reason": "based on cross-source consistency",
    "sources": ["Google Play", "Forums/Community"],
}


class TestNoDuplicateQuotes:
    def test_same_quote_in_two_findings_flagged(self):
        findings = [
            {**VALID_FINDING, "question": "Q1"},
            {**VALID_FINDING, "question": "Q2"},  # same quotes
        ]
        _, issues = validate.validate_findings(findings, CORPUS_SET)
        dup_issues = [i for i in issues if i["issue_type"] == "DUPLICATE_QUOTE"]
        assert len(dup_issues) > 0, "Expected duplicate quote issues"

    def test_different_quotes_no_dup_issue(self):
        finding2 = {
            **VALID_FINDING,
            "question": "Q2",
            "representative_quotes": [
                {"text": "i can't find my old photos using the search", "source": "App Store", "rating": 2},
            ],
        }
        findings = [VALID_FINDING, finding2]
        _, issues = validate.validate_findings(findings, CORPUS_SET)
        dup_issues = [i for i in issues if i["issue_type"] == "DUPLICATE_QUOTE"]
        assert len(dup_issues) == 0


class TestRealQuoteRequired:
    def test_empty_quotes_flagged(self):
        finding = {**VALID_FINDING, "representative_quotes": []}
        _, issues = validate.validate_findings([finding], CORPUS_SET)
        no_quote_issues = [i for i in issues if i["issue_type"] == "NO_QUOTES"]
        assert len(no_quote_issues) == 1

    def test_hallucinated_quote_flagged(self):
        finding = {
            **VALID_FINDING,
            "representative_quotes": [
                {"text": "This quote was totally made up and does not exist in corpus", "source": "Google Play", "rating": 1},
            ],
        }
        _, issues = validate.validate_findings([finding], CORPUS_SET)
        hall_issues = [i for i in issues if i["issue_type"] == "HALLUCINATED_QUOTE"]
        assert len(hall_issues) == 1

    def test_verbatim_quote_passes(self):
        finding = {
            **VALID_FINDING,
            "representative_quotes": [
                {"text": "i scrolled for hours trying to find a prescription screenshot", "source": "Google Play", "rating": 1},
                {"text": "search doesn't work for face recognition it misses half the photos", "source": "Forums/Community", "rating": None},
            ],
        }
        _, issues = validate.validate_findings([finding], CORPUS_SET)
        hall_issues = [i for i in issues if i["issue_type"] == "HALLUCINATED_QUOTE"]
        assert len(hall_issues) == 0


class TestConfidenceScoreLogic:
    def test_score_above_70_with_single_source_flagged(self):
        finding = {
            **VALID_FINDING,
            "confidence_score": 85,
            "confidence_label": "High",
            "sources": ["Google Play"],  # Only 1 source — should cap at 70
        }
        _, issues = validate.validate_findings([finding], CORPUS_SET)
        conf_issues = [i for i in issues if i["issue_type"] == "CONFIDENCE_INFLATED"]
        assert len(conf_issues) == 1

    def test_score_above_70_with_two_sources_passes(self):
        finding = {
            **VALID_FINDING,
            "confidence_score": 80,
            "confidence_label": "High",
            "sources": ["Google Play", "Forums/Community"],  # 2 sources — OK
        }
        _, issues = validate.validate_findings([finding], CORPUS_SET)
        conf_issues = [i for i in issues if i["issue_type"] == "CONFIDENCE_INFLATED"]
        assert len(conf_issues) == 0

    def test_score_70_with_one_source_passes(self):
        finding = {**VALID_FINDING, "confidence_score": 70, "confidence_label": "Medium", "sources": ["Reddit"]}
        _, issues = validate.validate_findings([finding], CORPUS_SET)
        conf_issues = [i for i in issues if i["issue_type"] == "CONFIDENCE_INFLATED"]
        assert len(conf_issues) == 0


class TestSchemaCheck:
    def test_missing_field_flagged(self):
        finding = {k: v for k, v in VALID_FINDING.items() if k != "pm_insight"}
        _, issues = validate.validate_findings([finding], CORPUS_SET)
        missing_issues = [i for i in issues if i["issue_type"] == "MISSING_FIELD"]
        assert any("pm_insight" in i["detail"] for i in missing_issues)

    def test_valid_finding_passes_all_checks(self):
        passed, issues = validate.validate_findings([VALID_FINDING], CORPUS_SET)
        critical = [i for i in issues if i["issue_type"] in
                    ("MISSING_FIELD", "HALLUCINATED_QUOTE", "NO_QUOTES", "CONFIDENCE_INFLATED")]
        assert len(critical) == 0, f"Unexpected critical issues: {critical}"
