from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib import error, parse, request

JST = timezone(timedelta(hours=9))
QIITA_API_URL = "https://qiita.com/api/v2/items"
NOTION_QUERY_URL = "https://api.notion.com/v1/databases/{database_id}/query"
NOTION_PAGE_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"
GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
SLACK_CHAT_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    summary: str
    author: str
    likes: int
    published_at: str
    tags: list[str]


def load_env_from_file(filepath: str = "SlackApp.txt") -> None:
    path = Path(filepath)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" in line:
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value and not os.environ.get(key):
            os.environ[key] = value


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
    cleaned = re.sub(r"\*{1,3}|_{1,3}|~{1,2}", "", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def split_sentences(text: str) -> list[str]:
    pieces = re.split(r"(?<=[。！？!?])|\n+", text)
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
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized or len(normalized) <= max_length:
        return normalized

    sentences = split_sentences(normalized)
    if not sentences:
        return normalized

    selected: list[str] = []
    total = 0
    for sentence in sentences:
        gap = 1 if selected else 0
        if selected and total + gap + len(sentence) > max_length:
            break
        selected.append(sentence)
        total += gap + len(sentence)

    if selected:
        return " ".join(selected).strip()

    clauses = [part.strip() for part in re.split(r"(?<=[、,])", sentences[0]) if part.strip()]
    if clauses:
        chunked: list[str] = []
        total = 0
        for clause in clauses:
            gap = 1 if chunked else 0
            if chunked and total + gap + len(clause) > max_length:
                break
            if not chunked and len(clause) > max_length:
                return clause
            chunked.append(clause)
            total += gap + len(clause)
        if chunked:
            return " ".join(chunked).strip()

    return sentences[0].strip()


def normalize_summary_sentence(sentence: str, title: str) -> str:
    normalized = sentence.strip()
    if not normalized:
        return ""
    if title and normalized.startswith(title):
        normalized = normalized[len(title) :].lstrip("。:：- ")
    return normalized.strip()


def summarize_article_rule_based(title: str, body: str, max_length: int = 160) -> str:
    source = strip_markdown(body)
    if not source:
        return truncate_summary(title, max_length)

    sentences = split_sentences(source)
    if not sentences:
        return truncate_summary(source or title, max_length)

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
    deduped: list[str] = []
    seen: set[str] = set()
    for sentence in ordered_selected or selected:
        normalized = normalize_summary_sentence(sentence, title)
        signature = re.sub(r"\s+", "", normalized)
        if not normalized or signature in seen:
            continue
        seen.add(signature)
        deduped.append(normalized)

    core = " ".join(deduped).strip()
    if not core:
        core = source[:max_length]
    return truncate_summary(core, max_length)


def summarize_article_with_github_models(
    title: str,
    body: str,
    max_length: int = 160,
    *,
    fetcher: Callable[..., dict | list] = http_json,
) -> str:
    api_key = os.getenv("GHUB_MODELS_API_KEY")
    if not api_key:
        raise RuntimeError("Missing required environment variable: GHUB_MODELS_API_KEY")

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
                        "日本語で120〜180字程度、事実ベースで要点のみを1〜2文で返してください。"
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
    max_length: int = 160,
    *,
    mode: str | None = None,
    llm_fetcher: Callable[..., dict | list] = http_json,
) -> str:
    active_mode = (mode or os.getenv("SUMMARIZER_MODE", "llm")).lower()
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


def _fetch_qiita_items(
    *,
    query: str,
    fetcher: Callable[..., dict | list] = http_json,
) -> list[dict]:
    items: list[dict] = []
    page = 1
    per_page = 100

    while True:
        url = f"{QIITA_API_URL}?{parse.urlencode({'page': page, 'per_page': per_page, 'query': query})}"
        token = os.getenv("QIITA_API_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else None
        response = fetcher("GET", url, headers=headers)
        page_items = response if isinstance(response, list) else []
        if not page_items:
            break
        items.extend(page_items)
        if len(page_items) < per_page:
            break
        page += 1

    return items


def _sort_qiita_items(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda item: (
            -(item.get("likes_count", 0) or 0),
            item.get("created_at", ""),
            item.get("title", ""),
        ),
    )


def fetch_qiita_trending_articles(
    *,
    lookback_days: int,
    limit: int = 20,
    fetcher: Callable[..., dict | list] = http_json,
    now: datetime | None = None,
) -> list[Article]:
    reference = now.astimezone(JST) if now else datetime.now(JST)
    since = (reference - timedelta(days=lookback_days)).date().isoformat()
    query = f"created:>{since}"
    items = _fetch_qiita_items(query=query, fetcher=fetcher)
    articles = [article_from_qiita_item(item) for item in _sort_qiita_items(items)]
    return articles[:limit]


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


def build_slack_payload(articles: list[Article], now: datetime | None = None) -> dict:
    reference = now.astimezone(JST) if now else datetime.now(JST)
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Qiitaトレンド Top {len(articles)}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{reference.strftime('%Y-%m-%d')}* の注目記事です。"
                    "順位、likes、タグを見やすく整理しています。"
                ),
            },
        },
    ]

    for index, article in enumerate(articles, start=1):
        tags = " ".join(f"#{tag}" for tag in article.tags) if article.tags else "なし"
        blocks.extend(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"*{index}位* <{article.url}|{article.title}>\n"
                            f"> {article.summary}"
                        ),
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f":thumbsup: *{article.likes} likes*"},
                        {
                            "type": "mrkdwn",
                            "text": f":bust_in_silhouette: {article.author or 'unknown'}",
                        },
                        {"type": "mrkdwn", "text": f":label: {tags}"},
                    ],
                },
                {"type": "divider"},
            ]
        )

    if blocks[-1]["type"] == "divider":
        blocks.pop()

    return {"blocks": blocks}


def build_slack_thread_reply_payload(index: int, article: Article) -> dict:
    tags = " ".join(f"#{tag}" for tag in article.tags) if article.tags else "なし"
    return {
        "text": f"{index}位: {article.title}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{index}位* <{article.url}|{article.title}>\n> {article.summary}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f":thumbsup: *{article.likes} likes*"},
                    {
                        "type": "mrkdwn",
                        "text": f":bust_in_silhouette: {article.author or 'unknown'}",
                    },
                    {"type": "mrkdwn", "text": f":label: {tags}"},
                ],
            },
        ],
    }


def _timestamp(now: datetime | None = None) -> str:
    reference = now.astimezone(JST) if now else datetime.now(JST)
    return reference.strftime("%Y%m%d")


def _to_iso(reference: datetime | None = None) -> str:
    current = reference.astimezone(JST) if reference else datetime.now(JST)
    return current.isoformat()


def _latest_file(pattern: str, output_dir: str = "articles") -> str:
    files = sorted(Path(output_dir).glob(pattern))
    if not files:
        raise RuntimeError(f"No file found for pattern: {output_dir}/{pattern}")
    return str(files[-1])


def fetch_article_info(
    *,
    lookback_days: int,
    limit: int = 20,
    fetcher: Callable[..., dict | list] = http_json,
    now: datetime | None = None,
) -> list[dict]:
    reference = now.astimezone(JST) if now else datetime.now(JST)
    since = (reference - timedelta(days=lookback_days)).date().isoformat()
    query = f"created:>{since}"
    items = _fetch_qiita_items(query=query, fetcher=fetcher)
    results: list[dict] = []
    for item in _sort_qiita_items(items)[:limit]:
        results.append(
            {
                "title": (item.get("title") or "").strip(),
                "url": item.get("url") or "",
                "body": item.get("body") or item.get("rendered_body") or "",
                "author": item.get("user", {}).get("id", ""),
                "likes": item.get("likes_count", 0),
                "published_at": item.get("created_at", ""),
                "tags": [tag.get("name") for tag in item.get("tags", []) if tag.get("name")],
            }
        )
    return results


def save_raw_articles(
    raw_articles: list[dict],
    *,
    output_dir: str = "articles",
    now: datetime | None = None,
) -> str:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    output_path = directory / f"raw_{_timestamp(now)}.json"
    payload = {
        "fetched_at": _to_iso(now),
        "count": len(raw_articles),
        "articles": raw_articles,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_path)


def load_raw_articles(input_path: str | None = None, *, output_dir: str = "articles") -> list[dict]:
    target = input_path or _latest_file("raw_*.json", output_dir=output_dir)
    data = json.loads(Path(target).read_text(encoding="utf-8"))
    return data.get("articles", [])


def summarize_and_format(
    raw_articles: list[dict],
    *,
    summarizer_mode: str | None = None,
    require_llm_success: bool = True,
) -> list[Article]:
    articles: list[Article] = []
    mode = (summarizer_mode or os.getenv("SUMMARIZER_MODE", "llm")).lower()
    for item in raw_articles:
        title = (item.get("title") or "").strip()
        body = item.get("body") or ""
        if require_llm_success and mode in {"llm", "github", "github_models"}:
            summary = summarize_article_with_github_models(title, body)
        else:
            summary = summarize_article(title, body, mode=mode)
        articles.append(
            Article(
                title=title,
                url=item.get("url") or "",
                summary=summary,
                author=item.get("author") or "",
                likes=int(item.get("likes", 0) or 0),
                published_at=item.get("published_at") or "",
                tags=[tag for tag in (item.get("tags") or []) if isinstance(tag, str) and tag],
            )
        )
    return articles


def save_processed_articles(
    articles: list[Article],
    *,
    output_dir: str = "articles",
    now: datetime | None = None,
) -> str:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    output_path = directory / f"processed_{_timestamp(now)}.json"
    payload = {
        "processed_at": _to_iso(now),
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
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output_path)


def load_processed_articles(
    input_path: str | None = None,
    *,
    output_dir: str = "articles",
) -> list[Article]:
    target = input_path or _latest_file("processed_*.json", output_dir=output_dir)
    data = json.loads(Path(target).read_text(encoding="utf-8"))
    rows = data.get("articles", [])
    return [
        Article(
            title=row.get("title") or "",
            url=row.get("url") or "",
            summary=row.get("summary") or "",
            author=row.get("author") or "",
            likes=int(row.get("likes", 0) or 0),
            published_at=row.get("published_at") or "",
            tags=[tag for tag in (row.get("tags") or []) if isinstance(tag, str) and tag],
        )
        for row in rows
    ]


def build_slack_thread_parent_payload(
    articles: list[Article],
    now: datetime | None = None,
) -> dict:
    reference = now.astimezone(JST) if now else datetime.now(JST)
    lines = [f"• {index}位 {article.title}" for index, article in enumerate(articles, start=1)]
    digest = "\n".join(lines[:10])
    return {
        "text": f"Qiitaトレンド Top {len(articles)} ({reference.strftime('%Y-%m-%d')})",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Qiitaトレンド Top {len(articles)}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{reference.strftime('%Y-%m-%d')}* の注目記事です。"
                        "詳細はこのスレッドに投稿します。"
                    ),
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": digest},
            },
        ],
    }


def build_slack_thread_summary_reply_payload(articles: list[Article]) -> dict:
    blocks: list[dict] = []
    for index, article in enumerate(articles, start=1):
        tags = " ".join(f"#{tag}" for tag in article.tags) if article.tags else "なし"
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{index}位* <{article.url}|{article.title}>\n"
                        f"> {article.summary}\n"
                        f":thumbsup: {article.likes} likes / :bust_in_silhouette: {article.author or 'unknown'} / :label: {tags}"
                    ),
                },
            }
        )

    return {
        "text": f"詳細まとめ ({len(articles)}件)",
        "blocks": blocks,
    }


def save_slack_message_backup(
    articles: list[Article],
    *,
    output_dir: str = "message",
    now: datetime | None = None,
) -> str:
    reference = now.astimezone(JST) if now else datetime.now(JST)
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    output_path = directory / f"{reference.strftime('%Y%m%d')}.md"
    lines = [
        f"# Qiitaトレンド Top {len(articles)} ({reference.strftime('%Y-%m-%d')})",
        "",
    ]

    for index, article in enumerate(articles, start=1):
        tags = " ".join(f"#{tag}" for tag in article.tags) if article.tags else "なし"
        lines.extend(
            [
                f"## {index}位: {article.title}",
                f"- URL: {article.url}",
                f"- Likes: {article.likes}",
                f"- Author: {article.author or 'unknown'}",
                f"- Tags: {tags}",
                f"- Summary: {article.summary}",
                "",
            ]
        )

    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return str(output_path)


def require_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")


def post_to_slack_thread(
    *,
    slack_bot_token: str,
    slack_channel: str,
    articles: list[Article],
    now: datetime | None = None,
    fetcher: Callable[..., dict | list] = http_json,
) -> None:
    headers = {"Authorization": f"Bearer {slack_bot_token}"}
    parent_payload = {
        "channel": slack_channel,
        **build_slack_thread_parent_payload(articles, now=now),
    }
    parent_response = fetcher(
        "POST",
        SLACK_CHAT_POST_MESSAGE_URL,
        headers=headers,
        body=parent_payload,
    )

    if not isinstance(parent_response, dict) or not parent_response.get("ok"):
        raise RuntimeError(f"Slack parent post failed: {parent_response}")

    thread_ts = parent_response.get("ts")
    if not thread_ts:
        raise RuntimeError("Slack parent post response missing ts")

    reply_payload = {
        "channel": slack_channel,
        "thread_ts": thread_ts,
        "reply_broadcast": False,
        **build_slack_thread_summary_reply_payload(articles),
    }
    reply_response = fetcher(
        "POST",
        SLACK_CHAT_POST_MESSAGE_URL,
        headers=headers,
        body=reply_payload,
    )
    if not isinstance(reply_response, dict) or not reply_response.get("ok"):
        raise RuntimeError(f"Slack thread reply failed: {reply_response}")


def notify_slack_thread(
    articles: list[Article],
    *,
    dry_run: bool = False,
) -> None:
    payload = build_slack_thread_parent_payload(articles)
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        reply = build_slack_thread_summary_reply_payload(articles)
        print(json.dumps(reply, ensure_ascii=False, indent=2))
        return

    slack_bot_token = require_env("SLACK_BOT_TOKEN")
    slack_channel = require_env("SLACK_CHANNEL")
    post_to_slack_thread(
        slack_bot_token=slack_bot_token,
        slack_channel=slack_channel,
        articles=articles,
    )


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
            "PublishedAt": {"date": {"start": article.published_at}},
            "NotifiedAt": {"date": {"start": notified_at.astimezone(JST).isoformat()}},
            "Read": {"checkbox": False},
            "Helpful": {"checkbox": False},
            "ReadAgain": {"checkbox": False},
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


def sync_notion(articles: list[Article]) -> None:
    notion_token = require_env("NOTION_TOKEN")
    database_id = require_env("NOTION_DATABASE_ID")
    save_articles_to_notion(
        articles,
        notion_token=notion_token,
        database_id=database_id,
    )


load_env_from_file()
load_env_from_file("Notion.txt")
load_env_from_file("Qiita.txt")
