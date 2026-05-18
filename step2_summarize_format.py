from __future__ import annotations

import os

from pipeline_steps import (
    load_raw_articles,
    save_processed_articles,
    save_slack_message_backup,
    summarize_and_format,
)


def main() -> int:
    input_path = os.getenv("STEP1_OUTPUT")
    notify_limit = int(os.getenv("QIITA_NOTIFY_LIMIT", "10"))
    summarizer_mode = os.getenv("SUMMARIZER_MODE")
    require_llm_success = os.getenv("REQUIRE_LLM_SUCCESS", "true").lower() in {
        "1",
        "true",
        "yes",
    }

    raw_articles = load_raw_articles(input_path)
    articles = summarize_and_format(
        raw_articles[:notify_limit],
        summarizer_mode=summarizer_mode,
        require_llm_success=require_llm_success,
    )
    output_path = save_processed_articles(articles)
    backup_path = save_slack_message_backup(articles)

    print(f"step2 complete: summarized {len(articles)} articles")
    print(f"processed output: {output_path}")
    print(f"message backup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
