from __future__ import annotations

import os

from pipeline_steps import load_processed_articles, sync_notion


def main() -> int:
    input_path = os.getenv("STEP2_OUTPUT")
    articles = load_processed_articles(input_path)
    sync_notion(articles)
    print(f"step4 complete: notion synced {len(articles)} articles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
