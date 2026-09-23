<div align="center">
  <h1>Google Photos — AI Discovery Engine</h1>
  <p>An AI-powered research platform analyzing why users struggle to find old photos, using real reviews from 4 major platforms.</p>

  <a href="https://google-photo-live-user-insights.vercel.app" target="_blank">
    <img src="https://img.shields.io/badge/Full_Research_Report-5e6ad2?style=for-the-badge&logo=googledocs&logoColor=white" alt="Full Research Report" />
  </a>
  <a href="https://github.com/suchijain78445/Google-photo-live-user-insights-" target="_blank">
    <img src="https://img.shields.io/badge/GitHub_Repository-090e1a?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Repository" />
  </a>
  <a href="docs/ARCHITECTURE.md" target="_blank">
    <img src="https://img.shields.io/badge/Docs_&_Architecture-090e1a?style=for-the-badge&logo=read-the-docs&logoColor=white" alt="Docs & Architecture" />
  </a>
</div>

<br>

## 🚀 Overview

Recall ingests 500+ real user reviews from the App Store, Google Play, Google Photos Community forums, and Reddit, then:

1. **Normalizes** all data into a unified format
2. **Filters** for photo retrieval/search-related content
3. **Clusters** reviews into 6 discovery themes using AI sentence embeddings
4. **Generates** 14 AI-researched findings (with verbatim quotes, PM insights, confidence scores)
5. **Validates** that no quotes are hallucinated
6. **Renders** everything in a dark-themed, premium interactive research dashboard

---

## Project Structure

```
├── scripts/
│   ├── ingest.py           # Normalize all 6 data files
│   ├── clean.py            # Dedupe, strip HTML, min-length filter
│   ├── filter_discovery.py # Keyword-filter for retrieval topics
│   ├── cluster.py          # MiniLM embeddings + K-Means clustering
│   ├── summarize.py        # Claude API → findings.json
│   ├── validate.py         # Verify quotes + confidence sanity
│   └── run_pipeline.py     # Orchestrates all steps
├── data/                   # Pipeline intermediate outputs
│   ├── raw_count.json
│   ├── raw_records.json
│   ├── cleaned.json
│   ├── filtered.json
│   ├── clusters.json
│   └── findings.json
├── dashboard/
│   ├── index.html          # Dashboard entry point
│   ├── styles.css          # Dark theme
│   ├── app.js              # SPA logic
│   └── findings.json       # Copy of data/findings.json
├── tests/
│   ├── test_ingest.py
│   └── test_validate.py
├── docs/
│   ├── PRD.md
│   └── ARCHITECTURE.md
├── Data reviews/           # Your raw input files
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

> Requires Python 3.10+. PyTorch is installed as a dependency of `sentence-transformers`.

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Running the Pipeline

### Run all steps

```bash
python scripts/run_pipeline.py
```

### Run specific steps

```bash
# Skip the LLM summarize step (use existing findings.json)
python scripts/run_pipeline.py --skip-summarize

# Run only ingest + clean + filter
python scripts/run_pipeline.py --only ingest clean filter

# Run just validate on existing findings
python scripts/run_pipeline.py --only validate
```

### Run steps individually

```bash
python scripts/ingest.py          # → data/raw_records.json
python scripts/clean.py           # → data/cleaned.json
python scripts/filter_discovery.py # → data/filtered.json
python scripts/cluster.py         # → data/clusters.json  (downloads MiniLM model first run)
python scripts/summarize.py       # → data/findings.json  (requires ANTHROPIC_API_KEY)
python scripts/validate.py        # → pass/fail report
```

> **Windows note:** Prefix with `$env:PYTHONUTF8=1;` to handle Unicode output correctly, e.g.:
> ```powershell
> $env:PYTHONUTF8=1; python scripts/run_pipeline.py
> ```

---

## Viewing the Dashboard

Open `dashboard/index.html` in your browser. Since findings are loaded via `fetch('findings.json')`, you need to serve the folder locally:

```bash
# Python built-in server (from the dashboard/ folder)
cd dashboard
python -m http.server 8080
```

Then visit: **http://localhost:8080**

### Ask AI (live questions)

The "Ask AI" input on the AI Research page calls the Anthropic API directly from the browser. To enable it, open the browser console and run:

```javascript
window.ANTHROPIC_API_KEY = 'sk-ant-your-key-here'
```

> **Security note:** In a production environment, proxy this through a backend server to avoid exposing your API key.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Tests cover:
- `test_ingest.py` — normalizer output shapes, Candy Crush filtering, empty body skipping, no duplicate IDs
- `test_validate.py` — hallucinated quote detection, duplicate quote detection, confidence inflation guard, schema checks

---

## Pipeline Output Summary (Real Data)

| Step | Output | Count |
|---|---|---|
| Ingest | Total records | 499 |
| Clean | After dedupe + min-length | 120 |
| Filter | Discovery-relevant | 71 |
| Cluster | Themes identified | 6 |
| Summarize | Research findings | 14 |

### Keyword Group Hits (from real data)

| Group | Matches |
|---|---|
| Search Failure | 30 |
| Memory Gaps | 25 |
| Face & People | 15 |
| Duplicate/Data Loss | 11 |
| Location | 8 |
| Scrolling | 7 |
| Screenshots/Docs | 6 |
| Context Retrieval | 6 |

---

## Data Sources

| Source | File | Records |
|---|---|---|
| App Store (Google Photos) | `appstore_reviews_reddit_shape.json` | 44 |
| Google Photos Community | `combined_all_matching_reviews 2.json` | 39 |
| Curated Pain Points | `curated_matching_pain_points 1.json` | 14 |
| Google Play | `dataset_google-play-scraper_*.json` | 100 |
| Research Dataset CSV | `Google Photos – User Research Dataset - Sheet1.csv` | 302 |

> The `dataset_app-store-reviews-scraper_*.json` file contains Candy Crush reviews and is automatically skipped by `ingest.py`.

---

## Adding New Data

1. Drop new `.json` or `.csv` files into `Data reviews/`
2. If the schema is new, add a normalizer function in `scripts/ingest.py`
3. Re-run the pipeline: `python scripts/run_pipeline.py`

See `docs/ARCHITECTURE.md` for full pipeline details.
