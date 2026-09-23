# Recall — Photo Retrieval Discovery Engine
## Product Requirements Document (PRD)

**Version:** 1.0 · **Date:** September 2026 · **Status:** Active Research

---

## 1. Problem Statement

Modern users accumulate thousands of photos in Google Photos but frequently cannot retrieve a specific photo they remember. The core failure is a **mental model mismatch**:

> Users remember photos through their **context, purpose, or emotional memory** ("I saved that prescription from my doctor"), but Google Photos requires them to recall **structured metadata** — a date, location, person, or object keyword.

When users can't provide these metadata anchors, they fall back to manual scrolling through years of photos — a process that is time-consuming, unreliable, and frustrating. This research project exists to **quantify and validate** this pain point using real user-generated evidence.

### Core Problem Breakdown

| Pain Point | Description |
|---|---|
| Excessive Scrolling | Users scroll through years of photos because search cannot interpret their contextual memory |
| Search-Memory Mismatch | Search results don't match what users actually remember about a photo |
| Face Search Overload | Face-based results narrow the search but still leave hundreds of photos to scroll through |
| Location Retrieval Failure | Location tags missing, inaccurate, or not surfaced during search |
| Screenshot Discovery | Screenshots (prescriptions, receipts, docs, quotes) cannot be retrieved by purpose |
| Context vs. Metadata Gap | Users know why they saved a photo but not when/where/what it contains |

---

## 2. Project Goals

1. **Validate** that difficulty finding old/specific photos is a real, recurring, severe user problem
2. **Quantify** the frequency and severity of each pain point using real review data
3. **Surface patterns** across 4 data sources (App Store, Google Play, Community Forums, Research Dataset)
4. **Generate structured research findings** with PM-level insights using an LLM pipeline
5. **Produce a shareable dashboard** for presenting findings to stakeholders

---

## 3. Target Users (of this Research Tool)

- **Product Managers** at Google Photos or photo-management competitors
- **UX Researchers** studying photo management behavior
- **Graduate researchers** investigating human-computer interaction with memory and photo retrieval
- **Engineers** looking for signal-backed feature opportunities

---

## 4. Research Questions

The pipeline generates structured answers for these 14 research questions:

1. What kinds of old photos do users struggle to retrieve?
2. What information do people actually remember about a photo?
3. What information have they forgotten when trying to find a photo?
4. How do users formulate searches when their memory is incomplete?
5. What features do users request most for finding old photos?
6. How do face and people recognition features affect photo retrieval?
7. Which retrieval problem is the most severe — search failure, memory gaps, or feature regressions?
8. How does location-based search fail users, and what would fix it?
9. Which user segments are more likely to experiment with alternative search methods?
10. What unmet needs emerge consistently across all discussions?
11. How do screenshots and document photos create a unique retrieval problem?
12. How does the mismatch between user memory (context/purpose) and system expectations (date/object/person) cause retrieval failure?
13. What workarounds do users adopt when Google Photos search fails them?
14. How does excessive scrolling affect UX and what triggers users to give up?

---

## 5. Success Metrics

| Metric | Target |
|---|---|
| Data sources ingested | 4+ |
| Findings generated | 14 |
| Findings with ≥2 source coverage | ≥ 10 |
| Verbatim quote validation pass rate | 100% |
| Confidence score accuracy (≤70 unless multi-source) | 100% |
| Dashboard renders findings correctly | Yes |
| Ask AI live feature works end-to-end | Yes |

---

## 6. Data Sources

| Source | File | Volume | Notes |
|---|---|---|---|
| App Store Reviews | `appstore_reviews_reddit_shape.json` | 44 records | Google Photos App Store reviews, Reddit-schema format |
| Google Photos Community | `combined_all_matching_reviews 2.json` | 39 records | Forum/community posts about search failures |
| Curated Pain Points | `curated_matching_pain_points 1.json` | 14 records | Hand-curated discovery pain points |
| Google Play Reviews | `dataset_google-play-scraper_...json` | 100 records | Raw Play Store scrape, filtered to Google Photos app |
| Research Dataset | `Google Photos – User Research Dataset - Sheet1.csv` | 302 records | AI-classified reviews with structured columns |

> **Note:** `dataset_app-store-reviews-scraper_...json` contains Candy Crush reviews and is automatically skipped by `ingest.py`.

---

## 7. Scope

### In Scope
- End-to-end Python pipeline (ingest → clean → filter → cluster → summarize → validate)
- 14 pre-generated research questions answered by Claude
- Dark-themed web dashboard with 5 sections
- Live "Ask AI" question input
- Unit tests for ingest and validate
- Full documentation

### Out of Scope
- Real-time review scraping
- User authentication
- Production backend / API hosting
- Multi-language review analysis
- Survey or interview data collection
