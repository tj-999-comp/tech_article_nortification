from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib import error, parse, request


QIITA_API_URL = "https://qiita.com/api/v2/items"
NOTION_QUERY_URL = "https://api.notion.com/v1/databases/{database_id}/query"
NOTION_PAGE_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"
JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    summary: str
    author: str
    published_at: str
    tags: list[str]


def http_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict | list | None = None,
) -> dict | list:
    payload = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    req = request.Request(url, data=payload, headers=request_headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read()
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", "ignore")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {message}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc

    if not raw:
        return {}

    text = raw.decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def strip_markdown(text: str) -> str:
    cleaned = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    cleaned = re.sub(r"`[^`]+`", " ", cleaned)
    cleaned = re.sub(r"!\[.*?\]\(.*?\)", " ", cleaned)
    cleaned = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def summarize_article(title: str, body: str, max_length: int = 100) -> str:
    source = strip_markdown(body)
    if not source:
        return title[:max_length]

    candidate = f"{title}。{source}"
    if len(candidate) <= max_length:
        return candidate
    return candidate[: max_length - 1].rstrip() + "…"


def article_from_qiita_item(item: dict) -> Article:
    tags = [tag["name"] for tag in item.get("tags", []) if tag.get("name")]
    title = item["title"].strip()
    body = item.get("body") or item.get("rendered_body") or ""
    return Article(
        title=title,
        url=item["url"],
        summary=summarize_article(title, body),
        author=item.get("user", {}).get("id", ""),
        published_at=item.get("created_at", ""),
        tags=tags,
    )


def fetch_qiita_trending_articles(
    *,
    lookback_days: int,
    limit: int = 5,
    fetcher: Callable[..., dict | list] = http_json,
    now: datetime | None = None,
) -> list[Article]:
    reference = now.astimezone(JST) if now else datetime.now(JST)
    since = (reference - timedelta(days=lookback_days)).date().isoformat()
    query = f"created:>{since} order:likes"
    url = f"{QIITA_API_URL}?{parse.urlencode({'page': 1, 'per_page': limit, 'query': query})}"
    items = fetcher("GET", url)
    return [article_from_qiita_item(item) for item in items][:limit]


def build_slack_payload(articles: list[Article], now: datetime | None = None) -> dict:
    reference = now.astimezone(JST) if now else datetime.now(JST)
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Qiita人気記事トップ{len(articles)}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{reference.strftime('%Y-%m-%d')} 時点でのおすすめ記事です。",
            },
        },
    ]

    for index, article in enumerate(articles, start=1):
        tags = ", ".join(article.tags) if article.tags else "タグなし"
        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*{index}. <{article.url}|{article.title}>*\n"
                            f"{article.summary}\n"
                            f"`author: {article.author or 'unknown'} / tags: {tags}`"
                        ),
                    },
                },
                {"type": "divider"},
            ]
        )

    if blocks[-1]["type"] == "divider":
        blocks.pop()

    return {"blocks": blocks}


def notion_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
    }


def notion_rich_text(value: str) -> list[dict]:
    if not value:
        return []
    return [{"text": {"content": value}}]


def build_notion_page_payload(
    article: Article,
    *,
    database_id: str,
    notified_at: datetime,
) -> dict:
    return {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {"title": notion_rich_text(article.title)},
            "URL": {"url": article.url},
            "Summary": {"rich_text": notion_rich_text(article.summary)},
            "Source": {"select": {"name": "Qiita"}},
            "Published At": {"date": {"start": article.published_at}},
            "Notified At": {"date": {"start": notified_at.astimezone(JST).isoformat()}},
            "Read": {"checkbox": False},
            "Read Date": {"date": None},
            "Helpful": {"checkbox": False},
            "Read Again": {"checkbox": False},
            "Author": {"rich_text": notion_rich_text(article.author)},
            "Tags": {"multi_select": [{"name": tag} for tag in article.tags]},
        },
    }


def notion_page_exists(
    *,
    notion_token: str,
    database_id: str,
    article_url: str,
    fetcher: Callable[..., dict | list] = http_json,
) -> bool:
    response = fetcher(
        "POST",
        NOTION_QUERY_URL.format(database_id=database_id),
        headers=notion_headers(notion_token),
        body={
            "filter": {
                "property": "URL",
                "url": {"equals": article_url},
            },
            "page_size": 1,
        },
    )
    return bool(response.get("results"))


def save_articles_to_notion(
    articles: list[Article],
    *,
    notion_token: str,
    database_id: str,
    fetcher: Callable[..., dict | list] = http_json,
    now: datetime | None = None,
) -> None:
    notified_at = now or datetime.now(timezone.utc)
    headers = notion_headers(notion_token)
    for article in articles:
        if notion_page_exists(
            notion_token=notion_token,
            database_id=database_id,
            article_url=article.url,
            fetcher=fetcher,
        ):
            continue
        fetcher(
            "POST",
            NOTION_PAGE_URL,
            headers=headers,
            body=build_notion_page_payload(
                article,
                database_id=database_id,
                notified_at=notified_at,
            ),
        )


def post_to_slack(
    webhook_url: str,
    payload: dict,
    *,
    fetcher: Callable[..., dict | list] = http_json,
) -> None:
    fetcher("POST", webhook_url, body=payload)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")


def main() -> int:
    lookback_days = int(os.getenv("QIITA_LOOKBACK_DAYS", "7"))
    articles = fetch_qiita_trending_articles(lookback_days=lookback_days)
    payload = build_slack_payload(articles)

    if os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"}:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    slack_webhook_url = require_env("SLACK_WEBHOOK_URL")
    notion_token = require_env("NOTION_TOKEN")
    notion_database_id = require_env("NOTION_DATABASE_ID")

    post_to_slack(slack_webhook_url, payload)
    save_articles_to_notion(
        articles,
        notion_token=notion_token,
        database_id=notion_database_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
