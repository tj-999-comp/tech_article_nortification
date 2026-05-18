from __future__ import annotations

import os

from pipeline_steps import load_processed_articles, notify_slack_thread


def _is_true(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes"}


def main() -> int:
    input_path = os.getenv("STEP2_OUTPUT")
    notify_limit = int(os.getenv("QIITA_NOTIFY_LIMIT", "10"))
    dry_run = _is_true(os.getenv("DRY_RUN"))

    articles = load_processed_articles(input_path)[:notify_limit]
    notify_slack_thread(articles, dry_run=dry_run)

    mode = "dry-run" if dry_run else "post"
    print(f"step3 complete: slack thread {mode} for {len(articles)} articles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
