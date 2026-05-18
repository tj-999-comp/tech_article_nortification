from __future__ import annotations

import os

from pipeline_steps import (
    fetch_article_info,
    load_processed_articles,
    notify_slack_thread,
    save_processed_articles,
    save_slack_message_backup,
    save_raw_articles,
    summarize_and_format,
    sync_notion,
)


def _is_true(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes"}


def _parse_steps(value: str) -> list[int]:
    if not value.strip():
        return []
    steps: list[int] = []
    for token in value.split(","):
        piece = token.strip()
        if not piece:
            continue
        if piece not in {"1", "2", "3", "4"}:
            raise RuntimeError("PIPELINE_STEPS must be comma-separated values from 1..4")
        step = int(piece)
        if step not in steps:
            steps.append(step)
    return steps


def main() -> int:
    until_step = int(os.getenv("PIPELINE_UNTIL_STEP", "3"))
    selected_steps = _parse_steps(os.getenv("PIPELINE_STEPS", ""))
    dry_run = _is_true(os.getenv("DRY_RUN"))
    lookback_days = int(os.getenv("QIITA_LOOKBACK_DAYS", "7"))
    limit = int(os.getenv("QIITA_FETCH_LIMIT", "20"))
    notify_limit = int(os.getenv("QIITA_NOTIFY_LIMIT", "10"))
    summarizer_mode = os.getenv("SUMMARIZER_MODE")
    require_llm_success = _is_true(os.getenv("REQUIRE_LLM_SUCCESS", "true"))

    if until_step < 1 or until_step > 4:
        raise RuntimeError("PIPELINE_UNTIL_STEP must be 1..4")

    steps = selected_steps or list(range(1, until_step + 1))

    raw_articles: list[dict] | None = None
    articles = None
    processed_path: str | None = None

    if 1 in steps:
        raw_articles = fetch_article_info(lookback_days=lookback_days, limit=limit)
        raw_path = save_raw_articles(raw_articles)
        print(f"step1 complete: {raw_path}")

    if 2 in steps:
        if raw_articles is None:
            raw_articles = fetch_article_info(lookback_days=lookback_days, limit=limit)
            raw_path = save_raw_articles(raw_articles)
            print(f"step1 complete: {raw_path}")
        articles = summarize_and_format(
            raw_articles[:notify_limit],
            summarizer_mode=summarizer_mode,
            require_llm_success=require_llm_success,
        )
        processed_path = save_processed_articles(articles)
        backup_path = save_slack_message_backup(articles)
        print(f"step2 complete: {processed_path}")
        print(f"step2 backup: {backup_path}")

    if 3 in steps:
        if articles is None:
            articles = load_processed_articles(processed_path)[:notify_limit]
        notify_slack_thread(articles, dry_run=dry_run)
        mode = "dry-run" if dry_run else "post"
        print(f"step3 complete: {mode}")

    if 4 in steps:
        if articles is None:
            articles = load_processed_articles(processed_path)[:notify_limit]
        sync_notion(articles)
        print("step4 complete")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
