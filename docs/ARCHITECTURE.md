# Recall — Architecture & Data Flow

## Overview

Recall is a 6-stage data pipeline followed by a static web dashboard. The pipeline reads raw user review data, normalizes and filters it, clusters it by theme, summarizes it with an LLM, validates the output, and writes `findings.json` for the dashboard.

```
Data reviews/ (raw files)
      │
      ▼
  [1] ingest.py ──────────→ data/raw_records.json
                             data/raw_count.json
      │
      ▼
  [2] clean.py ───────────→ data/cleaned.json
      │
      ▼
  [3] filter_discovery.py → data/filtered.json
      │
      ▼
  [4] cluster.py ─────────→ data/clusters.json
      │
      ▼
  [5] summarize.py ───────→ data/findings.json
                             dashboard/findings.json
      │
      ▼
  [6] validate.py ────────→ Console report (pass/fail)

  dashboard/index.html ───→ Loads dashboard/findings.json
```

---

## Stage Details

### Stage 1 — Ingest (`scripts/ingest.py`)

**Why:** Each data source has a different JSON/CSV schema. Ingest normalizes everything into a single record format `{id, source, text, url, rating}`.

**Handlers per source:**

| File | Key fields extracted | Filter logic |
|---|---|---|
| `appstore_reviews_reddit_shape.json` | `body` → text, `rating` | None (all are Google Photos) |
| `combined_all_matching_reviews 2.json` | `body` → text, `communityName` → source | None |
| `curated_matching_pain_points 1.json` | `body` → text | None |
| `dataset_app-store-reviews-scraper_*.json` | `text`, `score` | Skip unless URL contains `962194608` (Candy Crush filtered) |
| `dataset_google-play-scraper_*.json` | `text`, `score` | Skip unless `appId == com.google.android.apps.photos` |
| `*.csv` | `User Quote` column | Skip if text contains Candy Crush markers |

**Output:** `data/raw_records.json` (all normalized records), `data/raw_count.json` (stats)

---

### Stage 2 — Clean (`scripts/clean.py`)

**Why:** Raw records contain duplicates (same text in multiple files), very short reviews (≤30 chars), and HTML noise.

**Operations:**
1. Strip HTML tags
2. Normalize whitespace and remove zero-width characters
3. Drop entries with `len(text) < 30`
4. Deduplicate by MD5 hash of normalized lowercase text

**Output:** `data/cleaned.json`

---

### Stage 3 — Filter (`scripts/filter_discovery.py`)

**Why:** Not all reviews are about photo retrieval/discovery. We need to isolate the signal from general app feedback. 49 of 120 cleaned records are not retrieval-relevant.

**Keyword groups (9 thematic groups):**
- `search_failure` — search, find, can't find, no results, wrong results
- `memory_gaps` — forgot, remember, years ago, old photos, missing
- `location` — location, trip, travel, vacation, map, city, mountain
- `face_people` — face, person, recognize, facial, people album
- `screenshots_docs` — screenshot, prescription, receipt, document, instagram
- `scrolling` — scroll, browse, manually, scan, go through
- `context_retrieval` — purpose, context, why I took, intended, reason
- `duplicate_dataloss` — duplicate, deleted, gone, missing photos, sync
- `frustration_giving_up` — give up, frustrated, unusable, wasted time

A record is kept if it matches **at least one** keyword from any group.

**Output:** `data/filtered.json` (71 records)

---

### Stage 4 — Cluster (`scripts/cluster.py`)

**Why:** Grouping records by theme reveals the relative weight of each pain point and helps ensure the LLM sees representative examples per theme.

**Method:**
1. Embed all 71 texts using `sentence-transformers/all-MiniLM-L6-v2` (local, no API cost)
2. L2-normalize embeddings for cosine-like distance
3. K-Means with `n_clusters=6, n_init=20`
4. Map cluster IDs to human-readable theme names by comparing each cluster centroid to 6 seed phrase embeddings

**Themes (from real data):**

| Theme | Count |
|---|---|
| Location Granularity | 20 |
| Screenshot & Document Discovery | 15 |
| Memory Gaps & Scrolling | 14 |
| Context vs. Metadata Gap | 14 |
| Face & People Recognition | 4 |
| Search Reliability | 4 |

**Output:** `data/clusters.json` (records annotated with `cluster_id` and `cluster_theme`)

---

### Stage 5 — Summarize (`scripts/summarize.py`)

**Why:** The LLM converts raw review patterns into structured, PM-readable research findings with citations.

**Model:** Anthropic Claude (configurable via `ANTHROPIC_MODEL` in `.env`, default: `claude-3-5-haiku-20241022`)

**Process:**
1. Prepare a corpus prompt from all 71 filtered records (up to 80,000 chars)
2. For each of 14 research questions, call Claude with:
   - System prompt: UX researcher role, verbatim-quote-only instruction, JSON-schema enforcement
   - User prompt: question + full corpus + output schema
3. Parse and validate JSON; retry up to 3× on parse errors; respect rate limits

**Schema enforced:**
```json
{
  "question": "...",
  "executive_summary": "...",
  "key_findings": ["...", "...", "...", "...", "..."],
  "representative_quotes": [{"text": "...", "source": "...", "rating": null}],
  "pm_insight": "...",
  "confidence_score": 0-100,
  "confidence_label": "High|Medium|Low",
  "confidence_reason": "...",
  "sources": ["..."]
}
```

**Output:** `data/findings.json` + `dashboard/findings.json`

---

### Stage 6 — Validate (`scripts/validate.py`)

**Why:** LLMs can hallucinate quotes. This stage prevents fabricated evidence from reaching the dashboard.

**Checks:**
1. **Schema completeness** — all 9 required fields present
2. **Verbatim quote verification** — each quote text must appear verbatim (or as substring) in `filtered.json`
3. **Duplicate quote detection** — same quote text cannot appear in multiple findings
4. **Confidence inflation guard** — `confidence_score > 70` requires ≥ 2 independent sources
5. **Label-score consistency** — High must be ≥75, Low must be ≤44

**Output:** Console pass/fail report; exits with code 1 on failures

---

## Dashboard Architecture

The dashboard is a **static single-page application** (plain HTML/CSS/JS, no build step).

```
dashboard/
  index.html   ← 5 pages, sidebar nav, Ask AI input
  styles.css   ← Dark theme, design tokens, glassmorphism cards
  app.js       ← Data loading, page routing, finding renderer
  findings.json← Generated by summarize.py (copied from data/)
```

**Pages:**
| Page | Content |
|---|---|
| Dashboard | Stats overview, source breakdown, signal groups, problem statement |
| AI Research | All 14 findings rendered as cards + Ask AI live input |
| Customer Signals | 60 raw filtered quotes as signal cards |
| Product Opportunities | PM insights from each finding, clickable to finding detail |
| Insight Library | All findings searchable + filterable by confidence level |

**Ask AI live feature:**
- Calls `https://api.anthropic.com/v1/messages` directly from the browser
- Requires `window.ANTHROPIC_API_KEY` to be set in the browser console
- In production: proxy through a backend endpoint to avoid exposing the key
- Renders the response in the same finding card format as pre-generated findings

---

## Re-running When New Data Is Added

1. Drop new `.json` or `.csv` files into `Data reviews/`
2. If the new file has a new schema, add a handler in `scripts/ingest.py`
3. Run the full pipeline:
   ```
   python scripts/run_pipeline.py
   ```
4. Or skip the slow summarize step if findings are still valid:
   ```
   python scripts/run_pipeline.py --skip-summarize
   ```
5. Refresh `dashboard/index.html` in the browser

**Pipeline flags:**
- `--skip-summarize` — skip LLM step (use existing `findings.json`)
- `--skip-cluster` — skip embedding + clustering
- `--only ingest clean filter` — run only specific steps
