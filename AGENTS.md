# Tech Article Notification Agents

このプロジェクトで使用するカスタムAgents定義です。各エージェントは特定のタスク領域に特化しており、全体のオーケストレーションの下で動作します。

## Portfolio作業記録の公開契約

- このリポジトリは、`tj-999-comp/sandbox-pages`に作業記録を提供する生成元リポジトリである。
- 公開用の不変な`project_id`は`tech_article_nortification`とする。
- 公開対象は`work-records/md/work_record_###.md`と`work-records/metadata/work_record_###.yml`。番号は`001`から採番する。
- 公開方式は`a_rendered`であり、HTML・CSS・designは生成元で管理しない。A側rendererがHTMLを生成する。
- `Issues/Issue_###.md`は課題資料であり、作業記録の公開対象へ自動変換しない。
- 公開要求は、検証済みcommitの固定SHA、対象basename、`project_id`を使って行う。公開リポジトリのContents write権限を持つtokenは取得・保存・使用せず、cross-repository dispatchが必要な場合はActions実行だけを許可した専用Secretを使う。
- 詳細な入力契約と公開先は、sandbox-pagesの[公開ルール](https://github.com/tj-999-comp/sandbox-pages/blob/main/projects/README.md)を正本とする。

---

## 1. qiita-fetcher

**目的**: Qiitaの直近記事を人気順で取得

**責務**:
- Qiita APIから過去7日間に公開された記事を取得
- 人気順に並べ、最大20件の候補を抽出する
- 記事URL、タイトル、著者、いいね数などを抽出

**入力**: なし（GASの定期トリガーから起動）

**出力**: 
```json
[
  {
    "title": "記事タイトル",
    "url": "https://qiita.com/...",
    "author": "著者名",
    "likes": 123,
    "created_at": "2026-05-16T00:00:00Z"
  }
]
```

---

## 2. summarizer

**目的**: 記事から120〜180字程度の紹介文を生成

**責務**:
- 記事のURLにアクセスして内容を取得
- タイトルと内容から要約を生成（120〜180字程度）
- 記事の要点を簡潔に表現
- 読みやすいテキストに加工

**入力**: 
```json
{
  "url": "https://qiita.com/...",
  "title": "記事タイトル"
}
```

**出力**:
```json
{
  "url": "https://qiita.com/...",
  "title": "記事タイトル",
  "summary": "120〜180字程度の要約テキスト..."
}
```

---

## 3. notion-writer

**目的**: 記事情報をNotionのデータベースに保存

**責務**:
- Notion APIを使用してデータベースに記事を追加
- 記事URL、タイトル、要約を保存
- メタデータ（取得日時など）を記録
- Notionの管理プロパティ（読んだかどうか、日付、役に立ったか、繰り返し読みたいか）の初期化

**入力**:
```json
{
  "url": "https://qiita.com/...",
  "title": "記事タイトル",
  "summary": "120〜180字程度の要約テキスト...",
  "author": "著者名",
  "fetched_date": "2026-05-16"
}
```

**出力**:
```json
{
  "success": true,
  "notion_page_id": "xxxxx",
  "url": "https://qiita.com/..."
}
```

---

## 4. slack-notifier

**目的**: Slackチャネルに記事を通知

**責務**:
- Slack APIを使用してメッセージを送信
- 記事タイトル、要約、URLをフォーマット
- 見やすいメッセージレイアウト（ブロックレイアウト）を構築
- 複数記事を順序立てて通知

**入力**:
```json
{
  "articles": [
    {
      "title": "記事タイトル",
      "summary": "120〜180字程度の要約",
      "url": "https://qiita.com/...",
      "author": "著者名"
    }
  ],
  "slack_channel": "#tech-news"
}
```

**出力**:
```json
{
  "success": true,
  "slack_ts": "1234567890.123456"
}
```

---

## 5. orchestrator

**目的**: 全体フローを調整・管理

**責務**:
- GASの時間主導トリガーによる定期実行（毎週水曜・土曜の08:00 JST）
- 各エージェントの実行順序を制御
- qiita-fetcher → summarizer → slack-notifier → notion-writer の順序で実行
- エラーハンドリング（失敗時のリトライ、ログ記録）
- 実行結果の集約とレポート

**入力**: スケジュール設定、環境変数

**出力**: 実行ログ、エラーレポート

---

## 実行フロー

```
水曜・土曜 8:00 JST (GAS時間主導トリガー)
    ↓
[orchestrator] フロー開始
    ↓
[qiita-fetcher] 過去7日間の人気記事を最大20件取得
    ↓
    ├→ [summarizer] 通知対象最大10記事の要約生成
    ↓
[slack-notifier] Slackで通知
    ↓
[notion-writer] 通知対象記事をNotionに追加
    ↓
[orchestrator] 完了ログ記録
```

---

## 開発ガイド

各Agentの実装方法:
1. `src/agents/` ディレクトリ配下に各Agent用のディレクトリを作成
2. `index.ts` または `main.py` でエージェントロジックを実装
3. `interfaces.ts` で入出力型定義を記述
4. テストファイルを `__tests__/` に配置

---

## 環境変数

各Agentで必要な環境変数:
- `QIITA_API_TOKEN`: Qiita API アクセストークン
- `NOTION_TOKEN`: Notion API キー
- `NOTION_DATABASE_ID`: Notionデータベース ID
- `SLACK_BOT_TOKEN`: Slack Bot Token
- `SLACK_CHANNEL`: 通知先チャネルID
- `GHUB_MODELS_API_KEY`: GitHub Models API キー（LLM要約時）
- `QIITA_LOOKBACK_DAYS`: 取得対象期間（日数、既定値7）
- `QIITA_FETCH_LIMIT`: 取得候補数（既定値20）
- `QIITA_NOTIFY_LIMIT`: Slack通知・Notion同期数（既定値10）
