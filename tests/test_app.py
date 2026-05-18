import unittest
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib import parse
from unittest.mock import patch

import pipeline_steps as app


class SummarizeArticleTests(unittest.TestCase):
    def test_truncate_summary_never_hard_clips(self):
        text = "これは最初の文です。これはとても長い二つ目の文ですが、途中で切れてはいけません。"
        summary = app.truncate_summary(text, max_length=20)

        self.assertEqual(summary, "これは最初の文です。")

    def test_summarize_article_uses_body_and_limits_length(self):
        summary = app.summarize_article(
            "Python の便利な書き方",
            "# 見出し\nPython の書き方を丁寧に説明します。サンプルコードも含みます。" * 4,
            max_length=100,
        )

        self.assertIn("Python の書き方を丁寧に説明します", summary)
        self.assertLessEqual(len(summary), 100)
        self.assertTrue(summary.endswith("…") or summary.endswith("。"))

    def test_rule_based_summary_picks_important_sentence(self):
        summary = app.summarize_article(
            "Python API 認証の実装",
            (
                "導入です。背景説明です。"
                "今回の要点はPython API認証の実装手順と失敗しやすい設定の確認です。"
                "最後に補足があります。"
            ),
            max_length=100,
            mode="rule",
        )

        self.assertIn("API認証", summary)
        self.assertLessEqual(len(summary), 100)

    def test_llm_mode_uses_response_content(self):
        def fake_fetcher(method, url, **kwargs):
            self.assertEqual(method, "POST")
            self.assertIn("model", kwargs["body"])
            return {
                "choices": [
                    {
                        "message": {
                            "content": "認証方式の比較と実装時の落とし穴を整理し、設定確認の要点を100字で解説。"
                        }
                    }
                ]
            }

        with patch.dict(
            "os.environ",
            {
                "GHUB_MODELS_API_KEY": "dummy-token",
                "SUMMARIZER_MODE": "llm",
            },
            clear=False,
        ):
            summary = app.summarize_article(
                "Python API 認証の実装",
                "本文です。" * 30,
                max_length=100,
                llm_fetcher=fake_fetcher,
            )

        self.assertIn("実装", summary)
        self.assertLessEqual(len(summary), 100)

    def test_llm_mode_falls_back_to_rule_when_error(self):
        def failing_fetcher(method, url, **kwargs):
            raise RuntimeError("network error")

        with patch.dict(
            "os.environ",
            {
                "GHUB_MODELS_API_KEY": "dummy-token",
                "SUMMARIZER_MODE": "llm",
            },
            clear=False,
        ):
            summary = app.summarize_article(
                "Python API 認証の実装",
                "導入です。重要なのはPython API認証の実装とテスト自動化です。",
                max_length=100,
                llm_fetcher=failing_fetcher,
            )

        self.assertIn("Python API認証の実装", summary)
        self.assertLessEqual(len(summary), 100)

    def test_strip_markdown_removes_links_and_code(self):
        text = app.strip_markdown("`code` [Qiita](https://qiita.com) <b>bold</b>")
        self.assertEqual(text, "Qiita bold")


class QiitaFetchTests(unittest.TestCase):
    def test_fetch_qiita_trending_articles_builds_expected_query(self):
        captured = {}

        def fake_fetcher(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            return [
                {
                    "title": "記事タイトル",
                    "url": "https://qiita.com/example/items/1",
                    "body": "本文",
                    "user": {"id": "alice"},
                    "likes_count": 42,
                    "created_at": "2026-05-16T00:00:00+09:00",
                    "tags": [{"name": "Python"}],
                }
            ]

        articles = app.fetch_qiita_trending_articles(
            lookback_days=7,
            limit=5,
            fetcher=fake_fetcher,
            now=datetime(2026, 5, 16, 0, 0, tzinfo=timezone.utc),
        )

        parsed = parse.urlparse(captured["url"])
        query = parse.parse_qs(parsed.query)
        self.assertEqual(captured["method"], "GET")
        self.assertEqual(query["per_page"], ["5"])
        self.assertEqual(query["query"], ["created:>2026-05-09"])
        self.assertEqual(articles[0].summary, "本文")
        self.assertEqual(articles[0].likes, 42)

    def test_save_articles_snapshot_writes_json_under_articles_directory(self):
        article = app.Article(
            title="記事タイトル",
            url="https://qiita.com/example/items/1",
            summary="要約",
            author="alice",
            likes=42,
            published_at="2026-05-16T00:00:00+09:00",
            tags=["Python"],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "articles"
            output_path = app.save_articles_snapshot(
                [article],
                output_dir=str(output_dir),
                now=datetime(2026, 5, 16, 0, 0, tzinfo=timezone.utc),
            )

            self.assertTrue(Path(output_path).exists())
            self.assertTrue(str(output_path).endswith("20260516.json"))
            data = json.loads(Path(output_path).read_text(encoding="utf-8"))
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["articles"][0]["likes"], 42)
            self.assertEqual(data["articles"][0]["title"], "記事タイトル")


class SlackAndNotionTests(unittest.TestCase):
    def setUp(self):
        self.article = app.Article(
            title="記事タイトル",
            url="https://qiita.com/example/items/1",
            summary="100文字程度の紹介文です。",
            author="alice",
            likes=42,
            published_at="2026-05-16T00:00:00+09:00",
            tags=["Python", "Slack"],
        )

    def test_build_slack_payload_contains_article_sections(self):
        payload = app.build_slack_payload(
            [self.article],
            now=datetime(2026, 5, 16, 0, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(payload["blocks"][0]["type"], "header")
        self.assertIn(self.article.title, payload["blocks"][2]["text"]["text"])
        self.assertIn(self.article.summary, payload["blocks"][2]["text"]["text"])
        self.assertIn(str(self.article.likes), payload["blocks"][3]["elements"][0]["text"])
        self.assertIn("#Python", payload["blocks"][3]["elements"][2]["text"])

    def test_build_slack_thread_parent_payload_contains_digest(self):
        payload = app.build_slack_thread_parent_payload(
            [self.article],
            now=datetime(2026, 5, 16, 0, 0, tzinfo=timezone.utc),
        )

        self.assertIn("Qiitaトレンド Top 1", payload["text"])
        self.assertIn(self.article.title, payload["blocks"][2]["text"]["text"])

    def test_post_to_slack_thread_posts_parent_and_replies(self):
        calls: list[dict] = []

        def fake_fetcher(method, url, **kwargs):
            calls.append({"method": method, "url": url, "body": kwargs.get("body")})
            if len(calls) == 1:
                return {"ok": True, "ts": "123.456"}
            return {"ok": True, "ts": f"123.456.{len(calls)}"}

        app.post_to_slack_thread(
            slack_bot_token="xoxb-test",
            slack_channel="C12345",
            articles=[self.article, self.article],
            fetcher=fake_fetcher,
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["body"]["channel"], "C12345")
        self.assertNotIn("thread_ts", calls[0]["body"])
        self.assertEqual(calls[1]["body"]["thread_ts"], "123.456")

    def test_build_slack_thread_summary_reply_payload_contains_all_articles(self):
        payload = app.build_slack_thread_summary_reply_payload([self.article, self.article])
        text = payload["blocks"][0]["text"]["text"]

        self.assertIn("*1位*", text)
        self.assertIn("*2位*", text)
        self.assertIn(self.article.summary, text)

    def test_save_slack_message_backup_writes_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = app.save_slack_message_backup(
                [self.article],
                output_dir=tmpdir,
                now=datetime(2026, 5, 16, 0, 0, tzinfo=timezone.utc),
            )

            self.assertTrue(Path(output_path).exists())
            self.assertTrue(str(output_path).endswith("20260516.md"))
            content = Path(output_path).read_text(encoding="utf-8")
            self.assertIn("1位", content)
            self.assertIn("Likes: 42", content)
            self.assertIn("#Python #Slack", content)

    def test_build_notion_page_payload_sets_tracking_fields(self):
        payload = app.build_notion_page_payload(
            self.article,
            database_id="database-id",
            notified_at=datetime(2026, 5, 16, 0, 0, tzinfo=timezone.utc),
        )

        properties = payload["properties"]
        self.assertEqual(payload["parent"]["database_id"], "database-id")
        self.assertEqual(properties["URL"]["url"], self.article.url)
        self.assertFalse(properties["Read"]["checkbox"])
        self.assertFalse(properties["Helpful"]["checkbox"])
        self.assertFalse(properties["Read Again"]["checkbox"])

    def test_notion_page_exists_queries_by_url(self):
        captured = {}

        def fake_fetcher(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["body"] = kwargs["body"]
            return {"results": [{"id": "page-id"}]}

        exists = app.notion_page_exists(
            notion_token="secret",
            database_id="database-id",
            article_url=self.article.url,
            fetcher=fake_fetcher,
        )

        self.assertTrue(exists)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["body"]["filter"]["url"]["equals"], self.article.url)

    def test_http_json_accepts_plain_text_response(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"ok"

        with patch("pipeline_steps.request.urlopen", return_value=FakeResponse()):
            response = app.http_json("POST", "https://hooks.slack.com/services/example")

        self.assertEqual(response, {"raw": "ok"})


if __name__ == "__main__":
    unittest.main()
