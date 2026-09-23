"""
filter_discovery.py — Keyword-filters cleaned records for retrieval/search/memory-related content.

Keywords are organized into thematic groups matching the 14 research validation points:
  - Scrolling / browsing behavior
  - Search failure
  - Memory gaps (date, location, context)
  - Face/people recognition
  - Screenshot / document retrieval
  - Context-based retrieval
  - Duplicates / data loss

Input:  data/cleaned.json
Output: data/filtered.json
"""

import json
import re
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data")

# ─── Keyword groups ─────────────────────────────────────────────────────────────
KEYWORD_GROUPS = {
    "scrolling": [
        r"\bscroll\b", r"\bscrolling\b", r"\bscrolled\b",
        r"\bbrowse\b", r"\bbrowsing\b",
        r"\bmanually\b",
        r"\bscan\b", r"\bscanning\b",
        r"\bswipe\b", r"\bgo through\b", r"\bgoing through\b",
        r"\blook through\b", r"\bsearch through\b",
    ],
    "search_failure": [
        r"\bsearch\b", r"\bsearching\b", r"\bsearched\b",
        r"\bsearch (doesn'?t|does not|doesn'?t work|not working|fails?|broken|useless|terrible|bad|wrong|poor)\b",
        r"\bcan'?t find\b", r"\bcannot find\b", r"\bcould not find\b",
        r"\bdifficult to find\b", r"\bhard to find\b",
        r"\bno results\b", r"\bzero results\b", r"\bempty results\b",
        r"\bwrong results\b", r"\bunrelated (results|photos)\b",
        r"\bfilter\b", r"\bquery\b", r"\bkeyword\b",
        r"\bretrieve\b", r"\bretrieval\b",
    ],
    "memory_gaps": [
        r"\bforgot\b", r"\bforgotten\b", r"\bforget\b",
        r"\bremember\b", r"\bremembered\b", r"\bcan'?t remember\b",
        r"\bdon'?t remember\b", r"\bno idea\b",
        r"\bwhen (was|did|it was)\b",
        r"\bdate\b", r"\bwhen it was taken\b", r"\btime period\b",
        r"\byears ago\b", r"\bmonths ago\b", r"\bold photos\b", r"\bolder photos\b",
        r"\blong ago\b", r"\bback in\b",
        r"\bmissing\b", r"\blost\b", r"\bcannot locate\b",
        r"\bmemory\b", r"\bmemories\b",
    ],
    "location": [
        r"\blocation\b", r"\bwhere\b",
        r"\bplace\b", r"\bcity\b", r"\bcountry\b", r"\btravel\b",
        r"\btrip\b", r"\bvacation\b", r"\bholiday\b",
        r"\bmap\b", r"\bgps\b", r"\bgeotag\b", r"\bgeo\b",
        r"\bnearby\b", r"\barea\b", r"\bregion\b",
        r"\blocal\b", r"\baddress\b",
        r"\bmountain\b", r"\bbeach\b", r"\bpark\b",
    ],
    "face_people": [
        r"\bface\b", r"\bfaces\b",
        r"\bperson\b", r"\bpeople\b",
        r"\bfriend\b", r"\bfriends\b",
        r"\bfamily\b", r"\bwife\b", r"\bhusband\b",
        r"\bchild\b", r"\bchildren\b", r"\bkid\b", r"\bbaby\b",
        r"\brecognize\b", r"\brecognition\b",
        r"\bidentif\b",
        r"\bfacial\b",
        r"\bperson label\b", r"\bpeople album\b",
    ],
    "screenshots_docs": [
        r"\bscreenshot\b", r"\bscreenshots\b",
        r"\bdocument\b", r"\breceipt\b", r"\bbill\b", r"\bprescription\b",
        r"\bmedicine\b", r"\bmedical\b",
        r"\binstagram\b",
        r"\bquote\b", r"\bnote\b",
        r"\baddress\b", r"\bphone number\b",
        r"\bimportant photo\b", r"\bsaved image\b",
        r"\bsave\b.*\blater\b",
        r"\btext in photo\b", r"\bocr\b",
    ],
    "context_retrieval": [
        r"\bpurpose\b", r"\bcontext\b", r"\bmeaning\b",
        r"\bwhy (i|I) took\b", r"\breason\b",
        r"\bintend\b", r"\bintended\b", r"\bwanted to\b",
        r"\bnatural language\b", r"\bdescription\b",
        r"\brelated to\b", r"\brelated photos\b",
        r"\bsimilar\b", r"\bsuggest\b",
        r"\bcan'?t describe\b",
        r"\bdon'?t know what\b",
    ],
    "duplicate_dataloss": [
        r"\bduplicate\b", r"\bduplicates\b", r"\bduplication\b",
        r"\bdelet\b", r"\bdeleted\b", r"\bdeleted photos\b",
        r"\bgone\b", r"\bdisappear\b", r"\bdisappeared\b",
        r"\bmissing photos\b", r"\blost photos\b",
        r"\bbackup\b", r"\bsync\b",
        r"\bstorage\b",
        r"\bcorrupt\b",
    ],
    "frustration_giving_up": [
        r"\bgive up\b", r"\bgave up\b",
        r"\bfrustrat\b", r"\bannoy\b", r"\bunusable\b",
        r"\bimpossible\b", r"\bpointless\b", r"\buseless\b",
        r"\bnever find\b", r"\bcan'?t be found\b",
        r"\bwasted (time|hours|minutes)\b",
        r"\bgiven up\b", r"\babandoned\b",
        r"\bswitched to\b", r"\buse (icloud|apple|amazon|gallery)\b",
    ],
}

# Compile all patterns
ALL_PATTERNS = []
for group, patterns in KEYWORD_GROUPS.items():
    for pat in patterns:
        try:
            ALL_PATTERNS.append((group, re.compile(pat, re.IGNORECASE)))
        except re.error as e:
            print(f"  [WARN] Bad regex '{pat}': {e}")


def match_record(text: str) -> tuple[bool, list[str]]:
    """
    Returns (is_match, list_of_matched_groups).
    A record matches if it hits at least one keyword from any group.
    """
    matched_groups = set()
    for group, pattern in ALL_PATTERNS:
        if pattern.search(text):
            matched_groups.add(group)
    return bool(matched_groups), sorted(matched_groups)


def filter_records(records: list[dict]) -> tuple[list[dict], dict]:
    filtered = []
    stats = {
        "input": len(records),
        "matched": 0,
        "not_matched": 0,
        "by_group": {g: 0 for g in KEYWORD_GROUPS},
    }

    for rec in records:
        is_match, groups = match_record(rec["text"])
        if is_match:
            rec_out = {**rec, "_keyword_groups": groups}
            filtered.append(rec_out)
            stats["matched"] += 1
            for g in groups:
                stats["by_group"][g] += 1
        else:
            stats["not_matched"] += 1

    return filtered, stats


def main():
    in_path = OUTPUT_DIR / "cleaned.json"
    if not in_path.exists():
        print(f"❌ {in_path} not found. Run clean.py first.")
        return

    print(f"\n🔍 Filtering for discovery-related content...\n")

    with open(in_path, encoding="utf-8") as f:
        records = json.load(f)

    filtered, stats = filter_records(records)

    out_path = OUTPUT_DIR / "filtered.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    print(f"✅ Filtering complete.")
    print(f"   Input:    {stats['input']}")
    print(f"   Matched:  {stats['matched']}")
    print(f"   Skipped:  {stats['not_matched']}")
    print(f"\n   Keyword group hits:")
    for group, count in sorted(stats["by_group"].items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 40)
        print(f"     {group:<25} {count:>4}  {bar}")
    print(f"\n   Saved: {out_path}")

    # Also save a source breakdown
    source_counts = {}
    for r in filtered:
        src = r["source"]
        source_counts[src] = source_counts.get(src, 0) + 1
    print(f"\n   Filtered records by source:")
    for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"     {src:<30} {cnt}")


if __name__ == "__main__":
    main()
