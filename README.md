# tech_article_nortification

Qiita の人気記事 5 件を毎日 Slack に通知し、同じ記事リンクを Notion DB に蓄積するアプリケーションです。

## できること

- Qiita API から直近の人気記事を 5 件取得
- 取得した記事情報を `articles/YYYYMMDD.json` に保存
- 記事タイトルと本文から 120〜180 文字程度の紹介文を自動生成
- Slack へ通知（Webhook一括投稿 / スレッド投稿）
- Notion Database に記事を重複登録せず保存
- Notion 上で以下の状態を管理
  - Read
  - Read Date
  - Helpful
  - ReadAgain

## 現在の実装

- 共通処理は [pipeline_steps.py](pipeline_steps.py) に集約しています。
- 実行はステップ別スクリプトで行います。
  - [step1_fetch_articles.py](step1_fetch_articles.py)
  - [step2_summarize_format.py](step2_summarize_format.py)
  - [step3_notify_slack.py](step3_notify_slack.py)
  - [step4_sync_notion.py](step4_sync_notion.py)
- 一括実行は [run_pipeline.py](run_pipeline.py) を利用します。
- 日次実行は [daily-qiita-notify.yml](.github/workflows/daily-qiita-notify.yml) で実行します。
- Agent 分割の設計メモは [AGENTS.md](AGENTS.md) に記載しています。

## 実行ファイルの役割整理（2026-05-18時点）

| ファイル | 役割 | 主な用途 | 本番運用での位置づけ |
| --- | --- | --- | --- |
| `pipeline_steps.py` | コアロジック（取得/要約/Slack/Notion/保存） | 直接実行せず、各スクリプトから呼び出す | 必須 |
| `step1_fetch_articles.py` | Step1単体実行 | Qiita記事取得と生データ保存 | 必須 |
| `step2_summarize_format.py` | Step2単体実行 | 要約生成と加工データ保存 | 必須 |
| `step3_notify_slack.py` | Step3単体実行 | Slack通知 | 必須 |
| `step4_sync_notion.py` | Step4単体実行 | Notion同期 | 必須（Notion連携する場合） |
| `run_pipeline.py` | Step1-4のオーケストレーション | まとめて実行/任意ステップ実行 | 必須 |

削除済み（本番不要）:
- `_test_llm_api.py`: LLM要約の手動確認用スクリプト（固定本文でのデバッグ用途）
- `trigger_slack.py`: Slack payloadの手動確認用スクリプト（運用フローでは未使用）

`tests/` について:
- `tests/test_app.py` のみ存在し、`pipeline_steps.py` の要約・Slack・Notion処理の回帰テストを含みます。
- 本番「実行時」には不要ですが、変更時の品質担保に必要なため削除していません。

## 要約ロジック

記事の 120〜180 字程度の要約は 2 段階の処理で生成されます。

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
        │ 120〜180 字程度  │
        │ の要約文          │
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
5. 優先文を連結し、文単位で 160 字前後に調整

**特徴:**
- 外部 API 不要、高速
- ネットワーク障害の影響なし
- 必ず要約を返す

### LLM 要約（SUMMARIZER_MODE=llm）

GitHub Models API を呼び出し、タイトル・本文・ルール要約を参考に 120〜180 字程度の要約を生成します。

**入力データ:**
- `title`: 記事タイトル（文字列）
- `body`: 記事本文（Markdown 形式）
- `max_length`: 目標文字数（デフォルト: 160）

**必須環境変数と入力のマッピング:**

| 環境変数 | 用途 | 必須か | 例 |
|---------|------|-------|-----|
| `GHUB_MODELS_API_KEY` | HTTP リクエストの認証 | ✅ | `github_pat_xxxxx` |
| `GITHUB_MODELS_MODEL` | 使用するモデル | ❌（既定値あり） | `openai/gpt-4.1-mini` |
| `GITHUB_MODELS_URL` | API エンドポイント | ❌（既定値あり） | `https://models.inference.ai.azure.com/chat/completions` |

**API リクエストペイロード例:**

```json
{
  "model": "openai/gpt-4.1-mini",
  "messages": [
    {
      "role": "system",
      "content": "あなたは技術記事の要約者です。日本語で120〜180字程度、事実ベースで要点のみを1〜2文で返してください。出力は要約本文のみ。"
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
| `Authorization` ヘッダ | `Bearer {GHUB_MODELS_API_KEY}` | API キー認証 |
| `model` | `GITHUB_MODELS_MODEL` | 使用モデル（例: gpt-4.1-mini） |
| `messages[0].role` | `system` | システムプロンプト（要約者指示） |
| `messages[1].role` | `user` | ユーザー入力（記事情報） |
| `messages[1].content` | タイトル + ルール要約 + 本文 | 参考情報を含める |
| `temperature` | `0.2` | 再現性重視（低=安定、高=多様） |
| `max_tokens` | `220` | 最大出力長 |

**ユーザーメッセージの構成:**

```
タイトル: {記事のタイトル}
参考要約: {ルール要約ベースの160字前後の要約}
本文: {Markdown除去済みの本文先頭3000字}
```

**処理ステップ:**
1. タイトル・本文から ルール要約を事前生成（参考情報として使用）
2. 上記ペイロードを GitHub Models API へ HTTP POST
3. レスポンス `choices[0].message.content` から要約本文を抽出
4. 正規化後 160 字前後に文単位で調整

**失敗時の動作:**
- ネットワークエラー、タイムアウト、レスポンス不正 → ルール要約へ自動フォールバック
- 処理は常に続行（通知を止めない）

**特徴:**
- 複雑な記事でも要点を捉えやすい
- 文体が自然
- API 失敗時も配信継続

## 必要な環境変数

### 基本（必須）

- `SLACK_BOT_TOKEN`: Slack Bot Token（`chat:write` が必要）
- `SLACK_CHANNEL`: 投稿先チャンネル ID（例: `C0123456789`）
- `NOTION_TOKEN`: Notion Integration Token
- `NOTION_DATABASE_ID`: 保存先 Database ID
- `QIITA_LOOKBACK_DAYS`: 取得対象期間（日数、任意。既定値は `7`）
- `DRY_RUN`: `true` を指定すると外部通知せず payload を標準出力に表示

このアプリは親投稿 1 件 + 記事ごとのスレッド返信で通知します。
`SLACK_BOT_TOKEN` と `SLACK_CHANNEL` が未設定の場合、通常実行はエラーで停止します。

### 要約ロジック（任意）

- `SUMMARIZER_MODE`: `rule` または `llm`（既定値: `llm`）
  - `rule`: ルールベース要約のみ（常に安定）
  - `llm`: GitHub Models API を優先し、失敗時はルール要約へフォールバック
- `GHUB_MODELS_API_KEY`: GitHub Models API アクセストークン
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
| PublishedAt | Date |
| NotifiedAt | Date |
| Read | Checkbox |
| Read Date | Date |
| Helpful | Checkbox |
| ReadAgain | Checkbox |
| Tags | Multi-select |

## ローカル実行

```bash
python step1_fetch_articles.py
REQUIRE_LLM_SUCCESS=true GITHUB_MODELS_MODEL=gpt-4o-mini python step2_summarize_format.py
DRY_RUN=true python step3_notify_slack.py
```

## 分割実行（Step方式）

4つの処理を個別プログラムとして実行できます。

1. 記事情報の取得: `python step1_fetch_articles.py`
2. 記事の要約・メッセージ整形: `python step2_summarize_format.py`
3. Slack通知（親投稿 + スレッド返信1件に全記事要約を集約）: `python step3_notify_slack.py`
4. Notion連携: `python step4_sync_notion.py`

まとめて実行する場合は `run_pipeline.py` を使います。

```bash
# 今回の運用: Step3まで実行（Notion連携なし）
PIPELINE_UNTIL_STEP=3 DRY_RUN=false REQUIRE_LLM_SUCCESS=true GITHUB_MODELS_MODEL=gpt-4o-mini python run_pipeline.py

# 任意ステップだけ実行（例: Step1, Step2, Step4）
PIPELINE_STEPS=1,2,4 REQUIRE_LLM_SUCCESS=true GITHUB_MODELS_MODEL=gpt-4o-mini python run_pipeline.py
```

- `PIPELINE_UNTIL_STEP=3`: 1〜3のみ実行
- `PIPELINE_STEPS=1,2,4`: 指定したステップだけ実行（`PIPELINE_UNTIL_STEP`より優先）
- `DRY_RUN=false`: Slackへ実投稿
- `REQUIRE_LLM_SUCCESS=true`: LLM要約失敗時は停止（フォールバックしない）

補足:
- `step1_fetch_articles.py` 実行時に、`articles/` 配下の30日超過した `.json` を自動削除します。

## Stepとフロー図の対応

README冒頭の「要約ロジックのフロー図」は、記事1件に対する要約生成（Step2内）を説明した図です。
パイプライン全体との対応は次の通りです。

| パイプラインStep | 対応スクリプト | フロー上の担当範囲 |
| --- | --- | --- |
| Step1 | `step1_fetch_articles.py` | 図の「Qiita 記事取得 (title, body)」まで |
| Step2 | `step2_summarize_format.py` | 図の「SUMMARIZER_MODE 分岐」から「120〜180字の要約文」まで |
| Step3 | `step3_notify_slack.py` | 図の外（要約済みデータをSlackに通知） |
| Step4 | `step4_sync_notion.py` | 図の外（要約済みデータをNotionに同期） |

つまり、質問の「Step1は図のどこまでか」に対しては、
**Step1は記事取得までで、要約ロジック（図の分岐以降）はStep2の責務**です。

## テスト

```bash
python -m unittest discover -s tests -v
```

## 補足ドキュメント

- [AGENTS.md](AGENTS.md): Agent の責務分割案
- [.instructions.md](.instructions.md): 開発方針メモ
