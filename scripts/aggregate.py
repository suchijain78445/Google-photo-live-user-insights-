"""
aggregate.py — (Tasks 4, 5, 6)
Computes frequency tables, co-occurrence matrices, and opportunity scores from extracted.json
Outputs: core_answers.json (Q1-Q4) and opportunities.json
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data")

def main():
    extracted_path = OUTPUT_DIR / "extracted.json"
    answers_path = OUTPUT_DIR / "core_answers.json"
    opps_path = OUTPUT_DIR / "opportunities.json"

    if not extracted_path.exists():
        print(f"ERROR: {extracted_path} not found.")
        return

    with open(extracted_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    # ─── TASK 4: Core Questions Aggregation ─────────────────────────────────

    # Q1: photo_type distribution
    photo_types = defaultdict(list)
    # Q2: memory_anchors_present
    anchors_present = defaultdict(list)
    # Q3: memory_anchors_missing
    anchors_missing = defaultdict(list)
    # Q4: search_behavior segmented by memory completeness
    search_behavior = defaultdict(lambda: {"high_memory": [], "low_memory": []})

    # TASK 6: Co-occurrence & Opportunity Scoring
    # Track pairs of (missing_anchor, failure_point)
    co_occurrence = defaultdict(list)

    for rec in records:
        quote = rec.get("verbatim_quote", "")
        # Only attach quote evidence if it exists
        evidence = {"review_id": rec.get("review_id"), "quote": quote, "source": rec.get("source"), "user_segment": rec.get("user_segment_signal")}

        ptype = rec.get("photo_type", "unknown")
        photo_types[ptype].append(evidence)

        present = rec.get("memory_anchors_present", [])
        if not isinstance(present, list): present = []
        for p in present:
            anchors_present[p].append(evidence)

        missing = rec.get("memory_anchors_missing", [])
        if not isinstance(missing, list): missing = []
        for m in missing:
            anchors_missing[m].append(evidence)

        # Memory completeness: arbitrary threshold (e.g., >= 2 anchors present = high)
        mem_cat = "high_memory" if len(present) >= 2 else "low_memory"
        sb = rec.get("search_behavior", "unclear")
        search_behavior[sb][mem_cat].append(evidence)

        fp = rec.get("failure_point", "unclear")
        for m in missing:
            pair_key = f"{m} + {fp}"
            co_occurrence[pair_key].append(evidence)

    # Helper to sort frequencies and pick top 3 quotes
    def format_freq(freq_dict):
        results = []
        for k, items in freq_dict.items():
            valid_quotes = [i for i in items if i.get("quote")]
            results.append({
                "category": k,
                "count": len(items),
                "top_quotes": valid_quotes[:3]
            })
        return sorted(results, key=lambda x: x["count"], reverse=True)

    def format_behavior(behavior_dict):
        results = []
        for k, segments in behavior_dict.items():
            high = segments["high_memory"]
            low = segments["low_memory"]
            valid_quotes = [i for i in (high + low) if i.get("quote")]
            results.append({
                "behavior": k,
                "total_count": len(high) + len(low),
                "high_memory_count": len(high),
                "low_memory_count": len(low),
                "top_quotes": valid_quotes[:3]
            })
        return sorted(results, key=lambda x: x["total_count"], reverse=True)

    core_answers = {
        "Q1_photo_types": format_freq(photo_types),
        "Q2_anchors_present": format_freq(anchors_present),
        "Q3_anchors_missing": format_freq(anchors_missing),
        "Q4_search_behavior": format_behavior(search_behavior),
        "total_records": len(records)
    }

    with open(answers_path, "w", encoding="utf-8") as f:
        json.dump(core_answers, f, indent=2)

    # ─── TASK 6: Opportunity Scoring ───────────────────────────────────────
    
    opportunities = []
    for pair_key, items in co_occurrence.items():
        if "unclear" in pair_key:
            continue
        
        missing_anchor, failure_point = pair_key.split(" + ")
        freq = len(items)
        
        # Severity weighting
        severity = 1
        if failure_point in ["zero_results", "gave_up"]:
            severity = 3
        elif failure_point in ["wrong_results", "too_many_results"]:
            severity = 2
            
        score = freq * severity
        valid_quotes = [i for i in items if i.get("quote")]
        
        opportunities.append({
            "problem_pair": pair_key,
            "missing_anchor": missing_anchor,
            "failure_point": failure_point,
            "frequency": freq,
            "severity_multiplier": severity,
            "opportunity_score": score,
            "top_quotes": valid_quotes[:3]
        })

    # Sort descending by score
    opportunities = sorted(opportunities, key=lambda x: x["opportunity_score"], reverse=True)

    with open(opps_path, "w", encoding="utf-8") as f:
        json.dump(opportunities, f, indent=2)

    print(f"[AGGREGATE] Computed core answers and opportunities.")
    print(f"  -> Saved {answers_path.name}")
    print(f"  -> Saved {opps_path.name}")

if __name__ == "__main__":
    main()
