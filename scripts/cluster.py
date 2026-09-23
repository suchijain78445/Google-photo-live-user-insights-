"""
cluster.py — Embeds filtered records using sentence-transformers (all-MiniLM-L6-v2)
             and clusters into 6 discovery themes using K-Means.

Cluster themes:
  0: Search Reliability          — search fails, wrong results, no results
  1: Memory Gaps & Scrolling     — forgot date, scrolling through years
  2: Location Granularity        — location-based search failures
  3: Face & People Recognition   — face search limitations
  4: Screenshot & Doc Discovery  — screenshots, prescriptions, receipts
  5: Context vs. Metadata Gap    — purpose-based memory vs. date/object metadata

Input:  data/filtered.json
Output: data/clusters.json
"""

import json
import os
import numpy as np
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data")

N_CLUSTERS = 6

CLUSTER_LABELS = {
    0: "Search Reliability",
    1: "Memory Gaps & Scrolling",
    2: "Location Granularity",
    3: "Face & People Recognition",
    4: "Screenshot & Document Discovery",
    5: "Context vs. Metadata Gap",
}

# Seed phrases to help orient K-Means label assignment via nearest centroid matching
SEED_PHRASES = {
    "Search Reliability": "search doesn't work, wrong results, search is broken, no results returned",
    "Memory Gaps & Scrolling": "scrolling through years of photos, forgot when photo was taken, can't remember the date",
    "Location Granularity": "search by location doesn't work, can't find photos from a trip, location tag missing",
    "Face & People Recognition": "face recognition missing photos, searched by person still scrolling, face search fails",
    "Screenshot & Document Discovery": "can't find screenshot, lost prescription photo, can't find document screenshot",
    "Context vs. Metadata Gap": "remember why I took the photo but can't find it, photo has meaning but no metadata",
}


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed texts using sentence-transformers MiniLM."""
    print("  Loading sentence-transformers model (all-MiniLM-L6-v2)...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print(f"  Encoding {len(texts)} texts...")
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    return embeddings, model


def assign_cluster_labels(kmeans, model, seed_phrases: dict) -> dict:
    """
    Match KMeans cluster IDs to human-readable labels by finding which
    seed phrase is closest to each centroid.
    """
    seed_labels = list(seed_phrases.keys())
    seed_texts = list(seed_phrases.values())
    seed_embeddings = model.encode(seed_texts, convert_to_numpy=True)

    centroids = kmeans.cluster_centers_

    # For each centroid, find the nearest seed
    cluster_to_label = {}
    used_labels = set()
    for cluster_id in range(len(centroids)):
        centroid = centroids[cluster_id]
        # Cosine similarity to each seed
        sims = seed_embeddings @ centroid / (
            np.linalg.norm(seed_embeddings, axis=1) * np.linalg.norm(centroid) + 1e-8
        )
        # Pick highest-sim unused label
        sorted_idx = np.argsort(sims)[::-1]
        for idx in sorted_idx:
            label = seed_labels[idx]
            if label not in used_labels:
                cluster_to_label[cluster_id] = label
                used_labels.add(label)
                break

    return cluster_to_label


def cluster_records(records: list[dict]) -> tuple[list[dict], dict]:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import normalize

    texts = [r["text"] for r in records]
    embeddings, model = embed_texts(texts)

    # Normalize for cosine-like clustering
    embeddings_normed = normalize(embeddings)

    print(f"\n  Clustering into {N_CLUSTERS} themes...")
    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=20, max_iter=500)
    labels = kmeans.fit_predict(embeddings_normed)

    # Map cluster IDs to human labels
    cluster_to_label = assign_cluster_labels(kmeans, model, SEED_PHRASES)
    print(f"\n  Cluster label assignments:")
    for cid, label in cluster_to_label.items():
        print(f"    Cluster {cid} → {label}")

    # Annotate records
    annotated = []
    cluster_members = {label: [] for label in SEED_PHRASES.keys()}
    for rec, label_id in zip(records, labels):
        theme = cluster_to_label.get(int(label_id), f"Cluster {label_id}")
        rec_out = {**rec, "cluster_id": int(label_id), "cluster_theme": theme}
        annotated.append(rec_out)
        cluster_members[theme].append(rec["text"])

    # Build cluster summary
    cluster_stats = {}
    for cid, label in cluster_to_label.items():
        members = cluster_members[label]
        sources = {}
        for rec in [r for r in annotated if r["cluster_theme"] == label]:
            src = rec["source"]
            sources[src] = sources.get(src, 0) + 1
        cluster_stats[label] = {
            "cluster_id": cid,
            "count": len(members),
            "sources": sources,
            "sample_texts": members[:3],
        }

    return annotated, cluster_stats


def main():
    in_path = OUTPUT_DIR / "filtered.json"
    if not in_path.exists():
        print(f"❌ {in_path} not found. Run filter_discovery.py first.")
        return

    print(f"\n🧩 Clustering filtered records...\n")

    with open(in_path, encoding="utf-8") as f:
        records = json.load(f)

    if len(records) == 0:
        print("❌ No filtered records found.")
        return

    annotated, cluster_stats = cluster_records(records)

    out_path = OUTPUT_DIR / "clusters.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"records": annotated, "cluster_summary": cluster_stats}, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Clustering complete.")
    print(f"   Total records clustered: {len(annotated)}")
    print(f"\n   Theme breakdown:")
    for theme, stats in sorted(cluster_stats.items(), key=lambda x: -x[1]["count"]):
        bar = "█" * min(stats["count"], 40)
        print(f"     {theme:<35} {stats['count']:>4}  {bar}")
    print(f"\n   Saved: {out_path}")


if __name__ == "__main__":
    main()
