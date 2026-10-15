from __future__ import annotations

import argparse
import json
import platform
import time
import tracemalloc
from types import SimpleNamespace

from app.services.competitor_intelligence import _topic_counts

VOCABULARY = (
    "technical seo audit crawler indexing canonical metadata structured content",
    "search intelligence semantic retrieval evidence citation competitor analysis",
    "website performance page quality title headings internal links robots sitemap",
    "content strategy topic coverage analytics optimization research dashboard",
)
REPEATED_VOCABULARY = 25


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Profile competitor topic extraction on a synthetic text corpus."
    )
    parser.add_argument("--pages", type=int, default=1000)
    args = parser.parse_args()
    if args.pages < 1:
        parser.error("--pages must be greater than zero")

    body = " ".join(VOCABULARY * REPEATED_VOCABULARY)
    words_per_page = len(body.split())
    pages = [
        SimpleNamespace(title=f"Technical SEO analysis {index}", normalized_text=body)
        for index in range(args.pages)
    ]

    tracemalloc.start()
    started = time.perf_counter()
    topics = _topic_counts(pages)  # type: ignore[arg-type]
    elapsed = time.perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "pages": len(pages),
                "words_per_page": words_per_page,
                "total_words": words_per_page * len(pages),
                "distinct_candidates": len(topics),
                "elapsed_seconds": round(elapsed, 3),
                "tracemalloc_peak_mib": round(peak_bytes / 1024 / 1024, 2),
                "scope": (
                    "_topic_counts only; synthetic repeated vocabulary; excludes database, "
                    "semantic model, crawling, indexing, and frontend"
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
