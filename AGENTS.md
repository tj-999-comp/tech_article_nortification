# Tech Article Notification Agents

このプロジェクトで使用するカスタムAgents定義です。各エージェントは特定のタスク領域に特化しており、全体のオーケストレーションの下で動作します。

---

## 1. qiita-fetcher

**目的**: Qiitaのトレンド人気記事を取得

**責務**:
- Qiita API または Web スクレイピングでトレンド記事を取得
- 本日のトレンド上位5つの記事情報を抽出
- 記事URL、タイトル、著者、いいね数などを抽出

**入力**: なし（毎日実行）

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

**目的**: 記事から100字程度の紹介文を生成

**責務**:
- 記事のURLにアクセスして内容を取得
- タイトルと内容から要約を生成（約100字）
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
  "summary": "100字程度の要約テキスト..."
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
  "summary": "100字程度の要約テキスト...",
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
      "summary": "100字程度の要約",
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
- 毎日の定時実行スケジュール管理（例: 朝9時）
- 各エージェントの実行順序を制御
- qiita-fetcher → summarizer → notion-writer → slack-notifier の順序で実行
- エラーハンドリング（失敗時のリトライ、ログ記録）
- 実行結果の集約とレポート

**入力**: スケジュール設定、環境変数

**出力**: 実行ログ、エラーレポート

---

## 実行フロー

```
毎日 9:00 (定時)
    ↓
[orchestrator] フロー開始
    ↓
[qiita-fetcher] トレンド5記事を取得
    ↓
    ├→ [summarizer] 記事1の要約生成
    ├→ [summarizer] 記事2の要約生成
    ├→ [summarizer] 記事3の要約生成
    ├→ [summarizer] 記事4の要約生成
    ├→ [summarizer] 記事5の要約生成
    ↓
[notion-writer] 全記事をNotionに追加
    ↓
[slack-notifier] Slackで通知
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
- `NOTION_API_KEY`: Notion API キー
- `NOTION_DATABASE_ID`: Notionデータベース ID
- `SLACK_BOT_TOKEN`: Slack Bot Token
- `SLACK_CHANNEL`: 通知先チャネルID
