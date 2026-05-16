# tech_article_nortification

Qiita の人気記事 5 件を毎日 Slack に通知し、同じ記事リンクを Notion DB に蓄積するアプリケーションです。

## できること

- Qiita API から直近の人気記事を 5 件取得
- 取得した記事情報を `articles/YYYYMMDD.json` に保存
- 記事タイトルと本文から 100 文字前後の紹介文を自動生成
- Slack Incoming Webhook に通知
- Notion Database に記事を重複登録せず保存
- Notion 上で以下の状態を管理
  - Read
  - Read Date
  - Helpful
  - Read Again

## 現在の実装

- 実装本体は [app.py](app.py) の単一 Python スクリプトです。
- 要約生成関数
  - `summarize_article()`: エントリーポイント、モード判定
  - `summarize_article_rule_based()`: ルールベース要約
  - `summarize_article_with_github_models()`: GitHub Models API 呼び出し
  - `split_sentences()`: 文分割
  - `title_keywords()`: タイトルキーワード抽出
  - `score_sentence()`: 文スコアリング
  - `truncate_summary()`: 100 字調整
- 日次実行は [daily-qiita-notify.yml](.github/workflows/daily-qiita-notify.yml) で実行します。
- Agent 分割の設計メモは [AGENTS.md](AGENTS.md) に記載しています。

## 要約ロジック

記事の 100 字要約は 2 段階の処理で生成されます。

### フロー図

```
┌─────────────────────────────────┐
│  Qiita 記事取得                 │
│  (title, body)                  │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  環境変数: SUMMARIZER_MODE      │
└──────┬──────────────┬───────────┘
       │              │
   rule=1         llm=0
       │              │
       ▼              ▼
  ┌──────────┐  ┌──────────────────────┐
  │ ルール   │  │ LLM 要約             │
  │ ベース   │  │ (GitHub Models API)  │
  │ 要約     │  │                      │
  │ (高速)   │  │ + ルール要約を    │
  │          │  │   参考情報として送信 │
  └────┬─────┘  └──────┬───────────────┘
       │                │
       │           (失敗)│
       │         ┌──────▼────────┐
       │         │ ルール要約に  │
       │         │ フォールバック│
       │         └──────┬────────┘
       │                │
       └────────┬───────┘
                ▼
        ┌──────────────────┐
        │ 100 字の要約文   │
        │ (truncated)      │
        └──────────────────┘
```

### ルールベース要約（SUMMARIZER_MODE=rule）

本文を文単位に分割し、タイトルと内容から重要な文を抽出します。

**処理ステップ:**
1. 本文を Markdown 除去し、句読点で文分割
2. タイトルから 2 字以上のキーワード抽出
3. 各文にスコアを付与
   - タイトルキーワードのマッチ: +4 点/個
   - 技術用語（API、DB、認証、テスト等）: +2 点
   - 数値を含む: +1 点
   - 文長 15-120 字: 標準、短すぎ/-1 点、長すぎ/-1 点
4. スコア上位 3 文を元の順序で連結
5. タイトルと合わせて 100 字以内に調整

**特徴:**
- 外部 API 不要、高速
- ネットワーク障害の影響なし
- 必ず要約を返す

### LLM 要約（SUMMARIZER_MODE=llm）

GitHub Models API を呼び出し、タイトル・本文・ルール要約を参考に 100 字の要約を生成します。

**入力データ:**
- `title`: 記事タイトル（文字列）
- `body`: 記事本文（Markdown 形式）
- `max_length`: 目標文字数（デフォルト: 100）

**必須環境変数と入力のマッピング:**

| 環境変数 | 用途 | 必須か | 例 |
|---------|------|-------|-----|
| `GITHUB_MODELS_API_KEY` | HTTP リクエストの認証 | ✅ | `github_pat_xxxxx` |
| `GITHUB_MODELS_MODEL` | 使用するモデル | ❌（既定値あり） | `openai/gpt-4.1-mini` |
| `GITHUB_MODELS_URL` | API エンドポイント | ❌（既定値あり） | `https://models.inference.ai.azure.com/chat/completions` |

**API リクエストペイロード例:**

```json
{
  "model": "openai/gpt-4.1-mini",
  "messages": [
    {
      "role": "system",
      "content": "あなたは技術記事の要約者です。日本語で100字前後、事実ベースで要点のみを1文で返してください。出力は要約本文のみ。"
    },
    {
      "role": "user",
      "content": "タイトル: Python API 認証の実装\n参考要約: Python API 認証の実装。認証方式とテスト自動化の要点。\n本文: 導入文... [本文先頭3000字]"
    }
  ],
  "temperature": 0.2,
  "max_tokens": 220
}
```

**リクエストの構成要素:**

| 要素 | 値/内容 | 説明 |
|-----|--------|------|
| HTTP メソッド | POST | リクエストメソッド |
| URL | `GITHUB_MODELS_URL` | エンドポイント |
| `Authorization` ヘッダ | `Bearer {GITHUB_MODELS_API_KEY}` | API キー認証 |
| `model` | `GITHUB_MODELS_MODEL` | 使用モデル（例: gpt-4.1-mini） |
| `messages[0].role` | `system` | システムプロンプト（要約者指示） |
| `messages[1].role` | `user` | ユーザー入力（記事情報） |
| `messages[1].content` | タイトル + ルール要約 + 本文 | 参考情報を含める |
| `temperature` | `0.2` | 再現性重視（低=安定、高=多様） |
| `max_tokens` | `220` | 最大出力長 |

**ユーザーメッセージの構成:**

```
タイトル: {記事のタイトル}
参考要約: {ルール要約ベースの100字程度の要約}
本文: {Markdown除去済みの本文先頭3000字}
```

**処理ステップ:**
1. タイトル・本文から ルール要約を事前生成（参考情報として使用）
2. 上記ペイロードを GitHub Models API へ HTTP POST
3. レスポンス `choices[0].message.content` から要約本文を抽出
4. 正規化後 100 字以内に調整

**失敗時の動作:**
- ネットワークエラー、タイムアウト、レスポンス不正 → ルール要約へ自動フォールバック
- 処理は常に続行（通知を止めない）

**特徴:**
- 複雑な記事でも要点を捉えやすい
- 文体が自然
- API 失敗時も配信継続

## 必要な環境変数

### 基本（必須）

- `SLACK_WEBHOOK_URL`: Slack Incoming Webhook URL
- `NOTION_TOKEN`: Notion Integration Token
- `NOTION_DATABASE_ID`: 保存先 Database ID
- `QIITA_LOOKBACK_DAYS`: 取得対象期間（日数、任意。既定値は `7`）
- `DRY_RUN`: `true` を指定すると外部通知せず payload を標準出力に表示

### 要約ロジック（任意）

- `SUMMARIZER_MODE`: `rule` または `llm`（既定値: `rule`）
  - `rule`: ルールベース要約のみ（常に安定）
  - `llm`: GitHub Models API を優先し、失敗時はルール要約へフォールバック
- `GITHUB_MODELS_API_KEY`: GitHub Models API アクセストークン
  - `SUMMARIZER_MODE=llm` 時に必須
- `GITHUB_MODELS_MODEL`: 使用するモデル（既定値: `openai/gpt-4.1-mini`）
- `GITHUB_MODELS_URL`: GitHub Models エンドポイント（既定値: `https://models.inference.ai.azure.com/chat/completions`）

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
DRY_RUN=true python app.py
```

## テスト

```bash
python -m unittest discover -s tests -v
```

## 補足ドキュメント

- [AGENTS.md](AGENTS.md): Agent の責務分割案
- [.instructions.md](.instructions.md): 開発方針メモ
