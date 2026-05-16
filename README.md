# tech_article_nortification

Qiita の人気記事 5 件を毎日 Slack に通知し、同じ記事リンクを Notion DB に蓄積するアプリケーションです。

## できること

- Qiita API から直近の人気記事を 5 件取得
- 記事タイトルと本文から 100 文字前後の紹介文を自動生成
- Slack Incoming Webhook に通知
- Notion Database に記事を重複登録せず保存
- Notion 上で以下の状態を管理
  - Read
  - Read Date
  - Helpful
  - Read Again

## 必要な環境変数

- `SLACK_WEBHOOK_URL`: Slack Incoming Webhook URL
- `NOTION_TOKEN`: Notion Integration Token
- `NOTION_DATABASE_ID`: 保存先 Database ID
- `QIITA_LOOKBACK_DAYS`: 取得対象期間（日数、任意。既定値は `7`）
- `DRY_RUN`: `true` を指定すると外部通知せず payload を標準出力に表示

## Notion DB の想定プロパティ

次のプロパティを持つ Database を作成してください。

| プロパティ名 | 型 |
| --- | --- |
| Name | Title |
| URL | URL |
| Summary | Rich text |
| Source | Select |
| Published At | Date |
| Notified At | Date |
| Read | Checkbox |
| Read Date | Date |
| Helpful | Checkbox |
| Read Again | Checkbox |
| Author | Rich text |
| Tags | Multi-select |

## ローカル実行

```bash
cd /home/runner/work/tech_article_nortification/tech_article_nortification
DRY_RUN=true python app.py
```

## テスト

```bash
cd /home/runner/work/tech_article_nortification/tech_article_nortification
python -m unittest discover -s tests -v
```
