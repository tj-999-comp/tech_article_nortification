from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline_steps import fetch_article_info, save_raw_articles


def cleanup_old_article_jsons(*, output_dir: str = "articles", retention_days: int = 30) -> int:
    directory = Path(output_dir)
    if not directory.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted = 0
    for file_path in directory.glob("*.json"):
        modified_at = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
        if modified_at < cutoff:
            file_path.unlink(missing_ok=True)
            deleted += 1
    return deleted


def main() -> int:
    removed = cleanup_old_article_jsons()
    lookback_days = int(os.getenv("QIITA_LOOKBACK_DAYS", "7"))
    limit = int(os.getenv("QIITA_FETCH_LIMIT", "20"))

    raw_articles = fetch_article_info(lookback_days=lookback_days, limit=limit)
    output_path = save_raw_articles(raw_articles)
    print(f"step1 cleanup: deleted {removed} old json files")
    print(f"step1 complete: fetched {len(raw_articles)} articles")
    print(f"raw output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
