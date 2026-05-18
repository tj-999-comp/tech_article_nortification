# Issue 05: パイプライン分割・運用改善・Notion連携準備

## 背景
Qiita記事通知の処理を段階的に制御しやすくするため、以下の要件に基づいて実装を整理した。

1. 処理を step1〜step4 に分割して運用可能にする
2. step3 の Slack 投稿を「親投稿 + 返信1件に全記事要約集約」にする
3. `articles/` の JSON 蓄積を抑制する（gitignore + 30日超の自動削除）
4. 将来の Notion 連携に備えて step1,2,4 の実行経路を用意する
5. `app.py` 依存を廃止し、`pipeline_steps.py` に一本化する

---

## 実施内容

### 1) 実行フローの分割
- 追加:
  - `step1_fetch_articles.py`
  - `step2_summarize_format.py`
  - `step3_notify_slack.py`
  - `step4_sync_notion.py`
  - `run_pipeline.py`
- 共通処理を `pipeline_steps.py` に集約

### 2) Slack 投稿仕様の変更
- 変更前: 親投稿 + 記事ごとに返信（最大5件）
- 変更後: 親投稿 + 返信1件に全記事の要約を集約
- 関連実装:
  - `build_slack_thread_summary_reply_payload`
  - `post_to_slack_thread`
  - `notify_slack_thread`

### 3) articles の管理改善
- `.gitignore` に `articles/` を追加
- `step1_fetch_articles.py` に、`articles/*.json` のうち30日超過ファイルを削除する処理を追加

### 4) 任意ステップ実行
- `run_pipeline.py` に `PIPELINE_STEPS` を追加
  - 例: `PIPELINE_STEPS=1,2,4`
- `PIPELINE_STEPS` 指定時は `PIPELINE_UNTIL_STEP` より優先
- step1,2,4 をまとめて起動できる状態を確認

### 5) app.py 廃止
- `app.py` を削除
- step系スクリプト・ランナー・テストを `pipeline_steps.py` 参照に統一

---

## テスト・動作確認

### Unit Test
- 実行: `python3 -m unittest discover -s tests -v`
- 結果: 全テスト成功（16件）

### 連結テスト（step1→step3）
- 実行:
  - `python3 step1_fetch_articles.py`
  - `REQUIRE_LLM_SUCCESS=true GITHUB_MODELS_MODEL=gpt-4o-mini python3 step2_summarize_format.py`
  - `DRY_RUN=false python3 step3_notify_slack.py`
- 結果: 成功（記事取得、LLM要約、Slack投稿）

### 任意ステップ（step1,2,4）
- 実行: `PIPELINE_STEPS=1,2,4 REQUIRE_LLM_SUCCESS=true GITHUB_MODELS_MODEL=gpt-4o-mini python3 run_pipeline.py`
- 結果: 実行経路が有効で、Notion設定があれば step4 まで連携可能

---

## 補足
- `SlackApp.txt` の `key=value` 形式を自動読込し、不要な行（コメントや説明行）を無視する仕様に対応済み。
- 既存の運用コマンドは維持しつつ、段階実行と将来拡張（Notion）を両立できる構成にした。
