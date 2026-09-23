"""
run_pipeline.py — Orchestrates all pipeline steps in order:
  1. ingest.py    → data/raw_records.json + data/raw_count.json
  2. clean.py     → data/cleaned.json
  3. filter_discovery.py → data/filtered.json
  4. cluster.py   → data/clusters.json
  5. summarize.py → data/findings.json + dashboard/findings.json
  6. validate.py  → pass/fail report

Usage:
  python scripts/run_pipeline.py
  python scripts/run_pipeline.py --skip-summarize   (if you already have findings.json)
  python scripts/run_pipeline.py --only ingest clean filter
"""

import sys
import time
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))


def run_step(name: str, fn, *args, **kwargs):
    print(f"\n{'='*60}")
    print(f"  STEP: {name}")
    print(f"{'='*60}")
    start = time.time()
    try:
        fn(*args, **kwargs)
        elapsed = time.time() - start
        print(f"\n  ⏱  Completed in {elapsed:.1f}s")
        return True
    except SystemExit as e:
        if e.code != 0:
            print(f"\n  ❌ Step '{name}' exited with code {e.code}")
            return False
        return True
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n  ❌ Step '{name}' failed after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Run the Recall photo retrieval pipeline")
    parser.add_argument("--skip-summarize", action="store_true",
                        help="Skip the summarize step (use existing findings.json)")
    parser.add_argument("--skip-cluster", action="store_true",
                        help="Skip the cluster step")
    parser.add_argument("--only", nargs="+",
                        choices=["ingest", "clean", "filter", "cluster", "summarize", "validate"],
                        help="Run only specific steps")
    args = parser.parse_args()

    # Import all modules
    import ingest
    import clean
    import filter_discovery
    import cluster as cluster_mod
    import summarize
    import validate

    steps_to_run = args.only or ["ingest", "clean", "filter", "cluster", "summarize", "validate"]

    if args.skip_summarize and "summarize" in steps_to_run:
        steps_to_run.remove("summarize")
    if args.skip_cluster and "cluster" in steps_to_run:
        steps_to_run.remove("cluster")

    step_fns = {
        "ingest": ("1. Ingest — normalize all data sources", ingest.main),
        "clean": ("2. Clean — dedupe & strip noise", clean.main),
        "filter": ("3. Filter — keyword-filter for discovery topics", filter_discovery.main),
        "cluster": ("4. Cluster — embed & cluster into themes", cluster_mod.main),
        "summarize": ("5. Summarize — generate LLM findings", summarize.main),
        "validate": ("6. Validate — verify quotes & confidence", validate.main),
    }

    pipeline_start = time.time()
    results = {}

    for step_key in steps_to_run:
        label, fn = step_fns[step_key]
        success = run_step(label, fn)
        results[step_key] = success
        if not success and step_key not in ("validate",):
            print(f"\n⛔ Pipeline halted at step '{step_key}' — fix the error and re-run.")
            break

    # Summary
    total_elapsed = time.time() - pipeline_start
    print(f"\n{'='*60}")
    print(f"  PIPELINE SUMMARY  ({total_elapsed:.1f}s total)")
    print(f"{'='*60}")
    for step_key, success in results.items():
        icon = "✅" if success else "❌"
        label = step_fns[step_key][0]
        print(f"  {icon} {label}")

    # Show output files
    from dotenv import load_dotenv
    import os
    load_dotenv()
    output_dir = BASE_DIR / os.getenv("OUTPUT_DIR", "data")
    print(f"\n  Output files in {output_dir}/:")
    for fname in ["raw_count.json", "raw_records.json", "cleaned.json",
                  "filtered.json", "clusters.json", "findings.json"]:
        fpath = output_dir / fname
        if fpath.exists():
            size_kb = fpath.stat().st_size / 1024
            print(f"    ✓ {fname} ({size_kb:.1f} KB)")
        else:
            print(f"    - {fname} (not yet generated)")

    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
