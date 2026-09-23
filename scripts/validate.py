"""
validate.py — Validates findings.json for:

  1. Verbatim quote check: every quote in representative_quotes must appear
     verbatim (or near-verbatim with minor whitespace/punctuation normalization)
     in the filtered corpus (data/filtered.json).

  2. Confidence sanity check: confidence_score > 70 requires at least 2 independent
     sources listed in the 'sources' field.

  3. Schema check: every finding has required fields.

  4. No duplicate quotes: same quote text does not appear in more than one finding.

Input:  data/findings.json, data/filtered.json
Output: prints a validation report; exits with code 1 if any FAIL
"""

import json
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data")

REQUIRED_FIELDS = [
    "question", "executive_summary", "key_findings",
    "representative_quotes", "pm_insight",
    "confidence_score", "confidence_label", "confidence_reason", "sources",
]

VALID_SOURCES = {"Google Play", "App Store", "Reddit", "Forums/Community", "Research Dataset"}
VALID_CONFIDENCE_LABELS = {"High", "Medium", "Low"}


def normalize_for_match(text: str) -> str:
    """Normalize text for fuzzy matching — collapse whitespace, lowercase."""
    text = re.sub(r"\s+", " ", text).strip().lower()
    # Remove smart quotes
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    return text


def build_corpus_set(filtered_records: list[dict]) -> set[str]:
    """Build a set of normalized text strings from the filtered corpus."""
    return {normalize_for_match(r["text"]) for r in filtered_records}


def quote_in_corpus(quote_text: str, corpus_set: set[str]) -> bool:
    """
    Check if a quote appears verbatim (normalized) in the corpus.
    Also checks substring match (quote is a substring of any corpus entry).
    """
    norm_quote = normalize_for_match(quote_text)
    if norm_quote in corpus_set:
        return True
    # Substring match — quote might be a partial excerpt
    for corpus_text in corpus_set:
        if norm_quote in corpus_text or corpus_text in norm_quote:
            return True
    return False


def validate_findings(findings: list[dict], corpus_set: set[str]) -> tuple[bool, list[dict]]:
    """
    Returns (all_passed, list_of_issues).
    Each issue: {finding_index, question, issue_type, detail}
    """
    issues = []
    seen_quotes = {}  # quote_norm → (finding_index, question)

    for i, finding in enumerate(findings):
        q = finding.get("question", f"Finding #{i}")

        # 1. Schema check
        for field in REQUIRED_FIELDS:
            if field not in finding:
                issues.append({
                    "finding_index": i,
                    "question": q,
                    "issue_type": "MISSING_FIELD",
                    "detail": f"Missing required field: '{field}'",
                })

        # 2. Key findings count
        kf = finding.get("key_findings", [])
        if len(kf) < 1:
            issues.append({
                "finding_index": i,
                "question": q,
                "issue_type": "NO_KEY_FINDINGS",
                "detail": "key_findings is empty",
            })

        # 3. At least one quote
        quotes = finding.get("representative_quotes", [])
        if len(quotes) == 0:
            issues.append({
                "finding_index": i,
                "question": q,
                "issue_type": "NO_QUOTES",
                "detail": "representative_quotes is empty",
            })

        # 4. Verbatim quote check + duplicate detection
        for qi, quote_obj in enumerate(quotes):
            qt = quote_obj.get("text", "")
            if not qt:
                issues.append({
                    "finding_index": i,
                    "question": q,
                    "issue_type": "EMPTY_QUOTE",
                    "detail": f"Quote #{qi} has empty text",
                })
                continue

            if not quote_in_corpus(qt, corpus_set):
                issues.append({
                    "finding_index": i,
                    "question": q,
                    "issue_type": "HALLUCINATED_QUOTE",
                    "detail": f"Quote not found in corpus: \"{qt[:100]}...\"" if len(qt) > 100 else f"Quote not found in corpus: \"{qt}\"",
                })

            # Duplicate quote detection
            norm = normalize_for_match(qt)
            if norm in seen_quotes:
                prev_i, prev_q = seen_quotes[norm]
                issues.append({
                    "finding_index": i,
                    "question": q,
                    "issue_type": "DUPLICATE_QUOTE",
                    "detail": f"Quote also used in finding #{prev_i} ('{prev_q[:60]}'): \"{qt[:80]}\"",
                })
            else:
                seen_quotes[norm] = (i, q)

            # Source label check
            src = quote_obj.get("source", "")
            if src not in VALID_SOURCES:
                issues.append({
                    "finding_index": i,
                    "question": q,
                    "issue_type": "INVALID_SOURCE_LABEL",
                    "detail": f"Quote source '{src}' not in {VALID_SOURCES}",
                })

        # 5. Confidence score logic
        score = finding.get("confidence_score", 0)
        label = finding.get("confidence_label", "")
        sources = finding.get("sources", [])

        if score > 70 and len(sources) < 2:
            issues.append({
                "finding_index": i,
                "question": q,
                "issue_type": "CONFIDENCE_INFLATED",
                "detail": f"confidence_score={score} but only {len(sources)} source(s): {sources}",
            })

        if label not in VALID_CONFIDENCE_LABELS:
            issues.append({
                "finding_index": i,
                "question": q,
                "issue_type": "INVALID_CONFIDENCE_LABEL",
                "detail": f"confidence_label='{label}' not in {VALID_CONFIDENCE_LABELS}",
            })

        # Cross-check score vs label
        if label == "High" and score < 70:
            issues.append({
                "finding_index": i,
                "question": q,
                "issue_type": "LABEL_SCORE_MISMATCH",
                "detail": f"label='High' but score={score} (expected ≥75)",
            })
        elif label == "Low" and score > 45:
            issues.append({
                "finding_index": i,
                "question": q,
                "issue_type": "LABEL_SCORE_MISMATCH",
                "detail": f"label='Low' but score={score} (expected ≤44)",
            })

    all_passed = len(issues) == 0
    return all_passed, issues


def main():
    findings_path = OUTPUT_DIR / "findings.json"
    filtered_path = OUTPUT_DIR / "filtered.json"

    if not findings_path.exists():
        print(f"❌ {findings_path} not found. Run summarize.py first.")
        sys.exit(1)
    if not filtered_path.exists():
        print(f"❌ {filtered_path} not found. Run filter_discovery.py first.")
        sys.exit(1)

    print(f"\n🔎 Validating findings...\n")

    with open(findings_path, encoding="utf-8") as f:
        findings = json.load(f)
    with open(filtered_path, encoding="utf-8") as f:
        filtered_records = json.load(f)

    corpus_set = build_corpus_set(filtered_records)
    print(f"   Corpus size: {len(corpus_set)} unique normalized texts")
    print(f"   Findings to validate: {len(findings)}\n")

    all_passed, issues = validate_findings(findings, corpus_set)

    if all_passed:
        print("✅ ALL CHECKS PASSED")
        print(f"   {len(findings)} findings validated")
        total_quotes = sum(len(f.get("representative_quotes", [])) for f in findings)
        print(f"   {total_quotes} quotes verified verbatim")
    else:
        # Group by issue type
        by_type = {}
        for issue in issues:
            t = issue["issue_type"]
            by_type.setdefault(t, []).append(issue)

        print(f"⚠️  VALIDATION ISSUES FOUND: {len(issues)} issue(s)\n")
        for issue_type, issue_list in sorted(by_type.items()):
            print(f"   {'❌' if 'HALLUCINATED' in issue_type or 'MISSING' in issue_type else '⚠️ '} {issue_type} ({len(issue_list)})")
            for issue in issue_list[:3]:  # Show max 3 per type
                print(f"      Finding #{issue['finding_index']}: {issue['detail']}")
            if len(issue_list) > 3:
                print(f"      ... and {len(issue_list) - 3} more")

        # Exit with non-zero for CI
        sys.exit(1)


if __name__ == "__main__":
    main()
