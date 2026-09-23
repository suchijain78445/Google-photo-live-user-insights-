<div align="center">
  <h1>Google Photos — AI Discovery Engine</h1>
  <p>An AI-powered research platform analyzing why users struggle to find old photos, using real reviews from 4 major platforms to surface evidence-backed product insights for Google Photos Product Managers.</p>

  <a href="https://google-photo-live-user-insights.vercel.app" target="_blank">
    <img src="https://img.shields.io/badge/Live_Dashboard-5e6ad2?style=for-the-badge&logo=vercel&logoColor=white" alt="Live Dashboard" />
  </a>
  <a href="https://github.com/suchijain78445/Google-photo-live-user-insights-" target="_blank">
    <img src="https://img.shields.io/badge/GitHub_Repository-090e1a?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Repository" />
  </a>
  <a href="docs/ARCHITECTURE.md" target="_blank">
    <img src="https://img.shields.io/badge/Docs_&_Architecture-090e1a?style=for-the-badge&logo=read-the-docs&logoColor=white" alt="Docs & Architecture" />
  </a>
</div>

<br>

## Problem
The Google Photos team needs to understand the friction users face when attempting to retrieve and search for older memories. While app store reviews contain rich data, they are overwhelmingly skewed toward operational complaints (crashes, backups, sync issues) — making critical "discovery and retrieval intent" signals nearly impossible to isolate through manual or keyword-only analysis.

## Solution
A comprehensive NLP pipeline that:
* **Ingests and semantically clusters** 500+ reviews and community discussions from Google Play Store, App Store, Reddit, and Google Forums.
* **Processes** all data through a dedicated LLM summarization function.
* **Uses a PM-persona Groq prompt** to classify clusters as Discovery vs Operational and extract structured, actionable findings.
* **Validates** every extracted quote verbatim against the source text (zero hallucination tolerance).
* **Renders** findings into an interactive, dark-themed AI Discovery Dashboard deployed on Vercel.

## Dataset
| Source | Count |
| :--- | :--- |
| Google Play Store reviews | 150+ |
| Apple App Store reviews | 150+ |
| Reddit & Google Forums | 200+ |
| **Discovery clusters identified** | **6** |
| **Actionable PM Insights** | **14** |

## Research Questions
The pipeline is structured to answer core research questions, each grounded in verbatim evidence:

| # | Research Question | Report Section |
| :--- | :--- | :--- |
| Q1 | Why do users fail to find specific old photos? | Search & Retrieval Insights |
| Q2 | What friction exists in the current search experience? | Operational Themes |
| Q3 | How do users expect the search feature to behave? | AI & Smart Search |
| Q4 | What role does metadata (location, face, date) play? | Context Gaps |
| Q5 | What frustrations emerge repeatedly regarding organization? | Organization Barriers |

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a detailed component breakdown.

## Tech Stack
| Layer | Technology |
| :--- | :--- |
| **Language** | Python 3.10+ |
| **Backend / API proxy** | Flask, httpx |
| **Embeddings** | sentence-transformers (MiniLM) |
| **Clustering** | scikit-learn (K-Means) |
| **LLM Inference** | Groq API (llama-3.3-70b-versatile) |
| **Dashboard** | Vanilla HTML/CSS/JS · Chart.js |
| **Deployment** | Vercel (Serverless Python + Static UI) |

## Repository Structure

```text
Google-photo-live-user-insights-/
├── scripts/
│   ├── ingest.py           # Normalize all data files
│   ├── clean.py            # Dedupe, strip HTML, min-length filter
│   ├── filter_discovery.py # Keyword-filter for retrieval topics
│   ├── cluster.py          # MiniLM embeddings + K-Means clustering
│   ├── summarize.py        # Groq API → findings.json
│   ├── validate.py         # Verify quotes + confidence sanity
│   └── run_pipeline.py     # Main end-to-end orchestrator
├── data/
│   ├── raw_count.json
│   ├── cleaned.json
│   ├── filtered.json
│   ├── clusters.json
│   └── findings.json       # Final research insights
├── dashboard/
│   ├── index.html          # AI Discovery Dashboard UI
│   ├── styles.css          # Premium Dark theme
│   ├── app.js              # SPA logic and API calls
│   └── assets/             # Images and icons
├── api/
│   └── ask.py              # Vercel Serverless Function entry point
├── server.py               # Local Flask server & Vercel API routes
├── docs/
│   ├── PRD.md
│   └── ARCHITECTURE.md
├── Data reviews/           # Raw input files
├── requirements.txt        # Web server dependencies
├── requirements-ml.txt     # ML pipeline dependencies
├── vercel.json             # Vercel routing configuration
└── README.md
```

## Setup & Run

### Prerequisites
* Python 3.10+
* A free [Groq API key](https://console.groq.com/)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/suchijain78445/Google-photo-live-user-insights-.git
cd Google-photo-live-user-insights-

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
.venv\Scripts\activate     # Windows

# 3. Install Machine Learning dependencies
pip install -r requirements-ml.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and set: GROQ_API_KEY=your_api_key_here
```

### Run the Full Pipeline

```bash
python scripts/run_pipeline.py
```
This executes the complete multi-source pipeline in sequence:
1. **Ingest** — Normalizes App Store, Play Store, and Forum data
2. **Clean** — Deduplicates and noise-filters reviews
3. **Filter** — Isolates discovery and search-intent reviews
4. **Embed & Cluster** — Generates embeddings and groups reviews into semantic clusters
5. **Summarize** — Groq extracts structured PM insights
6. **Validate** — Verbatim quote validation against source text

## Key Findings

Top-line insight: Google Photos users struggle heavily with complex, multi-variable searches (e.g., trying to find a photo using a combination of location, time, and content). While simple face or location searches work well, the lack of robust natural language processing forces users to scroll endlessly to retrieve specific memories. 

| Finding | Confidence |
| :--- | :--- |
| Natural Language Search is highly requested but underperforming | 95% |
| False positives in AI categorizations create distrust | 92% |
| Users rely on manual albums due to search unreliability | 88% |

## Dashboard

The AI Discovery Dashboard presents all findings in an interactive internal PM workspace.

**Live:** [google-photo-live-user-insights.vercel.app](https://google-photo-live-user-insights.vercel.app/)

**Features:**
* **AI Discovery Assistant** — Select pre-loaded research questions or ask your own; returns structured answers with Executive Summary, Key Findings, Verbatim Quotes, PM Insight, and Confidence Score.
* **Interactive Architecture** — Visual flow of the data processing pipeline.
* **Global Navigation** — Dashboard · AI Research · Customer Signals · Product Opportunities · Insights Library.

## Deployment

The dashboard and its serverless AI API are deployed to [Vercel](https://vercel.com/) via GitHub auto-deployment.
* **Repository:** `suchijain78445/Google-photo-live-user-insights-`
* **Branch:** `main`
* **Configuration:** `vercel.json` maps `/api/ask` to the Flask backend and serves `dashboard/index.html` as the root UI.

Any push to `main` triggers an automatic Vercel redeploy.
