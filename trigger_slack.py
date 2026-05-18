from __future__ import annotations

import json
import os

import pipeline_steps as ps


def main() -> int:
    lookback_days = int(os.getenv("QIITA_LOOKBACK_DAYS", "7"))
    raw = ps.fetch_article_info(lookback_days=lookback_days, limit=5)
    articles = ps.summarize_and_format(raw, require_llm_success=False)

    payload = ps.build_slack_thread_parent_payload(articles)
    reply = ps.build_slack_thread_summary_reply_payload(articles)

    print("Parent payload:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("Reply payload:")
    print(json.dumps(reply, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
