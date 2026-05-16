from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib import error, parse, request


QIITA_API_URL = "https://qiita.com/api/v2/items"
NOTION_QUERY_URL = "https://api.notion.com/v1/databases/{database_id}/query"
NOTION_PAGE_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"
GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    summary: str
    author: str
    likes: int
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


def split_sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[。！？!?])\s+|\n+", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def title_keywords(title: str) -> list[str]:
    candidates = re.findall(r"[A-Za-z0-9_+#.-]+|[一-龥ぁ-んァ-ヶ]{2,}", title)
    return [word.lower() for word in candidates if len(word) >= 2]


def score_sentence(sentence: str, keywords: list[str]) -> int:
    lowered = sentence.lower()
    score = 0

    matched_keywords = sum(1 for keyword in set(keywords) if keyword and keyword in lowered)
    score += matched_keywords * 4

    technical_pattern = (
        r"API|DB|データベース|認証|テスト|性能|セキュリティ|エラー|実装|設計|"
        r"運用|自動化|CI|CD|Python|JavaScript|TypeScript|Go|Rust|Docker|AWS|Azure|GCP"
    )
    if re.search(technical_pattern, sentence, flags=re.IGNORECASE):
        score += 2
    if re.search(r"\d", sentence):
        score += 1

    if len(sentence) < 15:
        score -= 1
    if len(sentence) > 120:
        score -= 1
    return score


def truncate_summary(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def summarize_article_rule_based(title: str, body: str, max_length: int = 100) -> str:
    source = strip_markdown(body)
    if not source:
        return truncate_summary(title, max_length)

    sentences = split_sentences(source)
    if not sentences:
        return truncate_summary(f"{title}。{source}", max_length)

    keywords = title_keywords(title)
    scored = [
        (score_sentence(sentence, keywords), index, sentence)
        for index, sentence in enumerate(sentences)
    ]
    ranked = sorted(scored, key=lambda item: (-item[0], item[1]))

    selected = [sentence for _, _, sentence in ranked[:3]]
    if not selected:
        selected = sentences[:2]

    ordered_selected = [
        sentence for _, sentence in sorted((idx, s) for _, idx, s in ranked[:3])
    ]
    core = " ".join(ordered_selected or selected)
    candidate = f"{title}。{core}"
    return truncate_summary(candidate, max_length)


def summarize_article_with_github_models(
    title: str,
    body: str,
    max_length: int = 100,
    *,
    fetcher: Callable[..., dict | list] = http_json,
) -> str:
    api_key = os.getenv("GITHUB_MODELS_API_KEY")
    if not api_key:
        raise RuntimeError("Missing required environment variable: GITHUB_MODELS_API_KEY")

    source = strip_markdown(body)
    if not source:
        return truncate_summary(title, max_length)

    model = os.getenv("GITHUB_MODELS_MODEL", "openai/gpt-4.1-mini")
    endpoint = os.getenv("GITHUB_MODELS_URL", GITHUB_MODELS_URL)
    hint = summarize_article_rule_based(title, body, max_length=180)

    response = fetcher(
        "POST",
        endpoint,
        headers={"Authorization": f"Bearer {api_key}"},
        body={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "あなたは技術記事の要約者です。"
                        "日本語で100字前後、事実ベースで要点のみを1文で返してください。"
                        "出力は要約本文のみ。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"タイトル: {title}\n"
                        f"参考要約: {hint}\n"
                        f"本文: {source[:3000]}"
                    ),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 220,
        },
    )

    choices = response.get("choices") if isinstance(response, dict) else None
    if not choices:
        raise RuntimeError("GitHub Models response does not contain choices")

    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        content = " ".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("GitHub Models response content is empty")

    normalized = re.sub(r"\s+", " ", strip_markdown(content)).strip()
    return truncate_summary(normalized, max_length)


def summarize_article(
    title: str,
    body: str,
    max_length: int = 100,
    *,
    mode: str | None = None,
    llm_fetcher: Callable[..., dict | list] = http_json,
) -> str:
    active_mode = (mode or os.getenv("SUMMARIZER_MODE", "rule")).lower()
    if active_mode in {"llm", "github", "github_models"}:
        try:
            return summarize_article_with_github_models(
                title,
                body,
                max_length=max_length,
                fetcher=llm_fetcher,
            )
        except RuntimeError:
            return summarize_article_rule_based(title, body, max_length=max_length)
    return summarize_article_rule_based(title, body, max_length=max_length)


def article_from_qiita_item(item: dict) -> Article:
    tags = [tag["name"] for tag in item.get("tags", []) if tag.get("name")]
    title = item["title"].strip()
    body = item.get("body") or item.get("rendered_body") or ""
    return Article(
        title=title,
        url=item["url"],
        summary=summarize_article(title, body),
        author=item.get("user", {}).get("id", ""),
        likes=item.get("likes_count", 0),
        published_at=item.get("created_at", ""),
        tags=tags,
    )


def save_articles_snapshot(
    articles: list[Article],
    *,
    output_dir: str = "articles",
    now: datetime | None = None,
) -> str:
    reference = now.astimezone(JST) if now else datetime.now(JST)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    output_path = directory / f"{reference.strftime('%Y%m%d')}.json"
    payload = {
        "fetched_at": reference.isoformat(),
        "count": len(articles),
        "articles": [
            {
                "title": article.title,
                "url": article.url,
                "summary": article.summary,
                "author": article.author,
                "likes": article.likes,
                "published_at": article.published_at,
                "tags": article.tags,
            }
            for article in articles
        ],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(output_path)


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
    save_articles_snapshot(articles)
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
