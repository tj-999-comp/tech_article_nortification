# Issue_006: Notion送信フロー実装とテスト完了（2026-05-18）

## 概要

Notion Database への記事送信フロー（Step4）の実装完了と、全体テスト（Step1→Step2→Step4）の動作確認を完了しました。

## 実施内容

### 1. README.md の Notion DB スキーマ更新
- 新 DB プロパティ定義に合わせてテーブルを修正
- `Published At` → `PublishedAt`
- `Notified At` → `NotifiedAt`
- `Read Again` → `ReadAgain`
- `Author` プロパティを削除
- `Read Date` プロパティを削除

### 2. 環境変数読み込みの統一化
- `pipeline_steps.py` に `load_env_from_file("Notion.txt")` を追加
- SlackApp.txt と同様の方式で Notion.txt から環境変数を読み込み

### 3. build_notion_page_payload 関数の修正
- 新 DB スキーマに対応するようプロパティ名をコード内で更新
  - `Published At` → `PublishedAt`
  - `Notified At` → `NotifiedAt`
  - `Read Again` → `ReadAgain`
  - `Author` プロパティを削除
  - `Read Date` プロパティを削除
- 送信する Notion ページ構造を新スキーマに合わせて実装

### 4. Notion Integration と Database の接続確認
- Notion Integration "TechArticleNortification" の作成・設定
- 対象 Database への アクセス権付与
- ページレベルアクセス設定で Database を明示的に追加

### 5. DATABASE_ID の修正
- 初期設定で View ID を使用していたのを、正しい Database ID に修正
- URL から Database ID を抽出（ハイフン形式）

### 6. テスト実行

#### テスト1: テストデータでの送信テスト
```bash
STEP2_OUTPUT=articles/processed_20260518_notion_test.json python3 step4_sync_notion.py
```
- 結果：3件のダミー記事を Notion に送信成功

#### テスト2: 実運用フロー（Step1→Step2→Step4）
```bash
python3 step1_fetch_articles.py
REQUIRE_LLM_SUCCESS=true GITHUB_MODELS_MODEL=gpt-4o-mini python3 step2_summarize_format.py
python3 step4_sync_notion.py
```
- 結果：Qiita から 5 件取得、LLM 要約生成、Notion に 5 件送信成功

#### テスト3: 重複チェック機能の確認
```bash
# 1回目
python3 step4_sync_notion.py

# 2回目（同じデータを再送）
python3 step4_sync_notion.py
```
- 結果：同一 URL の記事は重複登録されず、2 回目でスキップされることを確認

#### テスト4: 新規データの追加確認
- 既存 5 件 + 架空の 6 件目テストデータを含むファイルで送信
- 結果：最初の 5 件はスキップ、6 件目のみ新規追加確認（Notion DB 記録数が 6 に増加）

## 成果物

### 修正ファイル
- [README.md](../README.md)：Notion DB プロパティ定義表の更新
- [pipeline_steps.py](../pipeline_steps.py)：
  - Notion.txt からの env 読み込み追加
  - `build_notion_page_payload` 関数の新スキーマ対応

### 作成・使用したテストファイル（テスト後削除）
- `articles/processed_20260518_notion_test.json`：3 件のダミーデータ
- `articles/processed_20260518_with_test_6th.json`：実データ + 6 件目テストデータ

## 動作確認結果

| 項目 | 結果 |
| --- | --- |
| Notion API 接続 | ✅ 成功 |
| プロパティ名マッピング | ✅ 成功 |
| 記事送信 | ✅ 成功（5 件） |
| 重複チェック | ✅ 動作確認 |
| 新規追加 | ✅ 動作確認 |

## 必要な環境設定

以下の情報を `Notion.txt` に配置：
```
NOTION_TOKEN=<Integration Token>
NOTION_DATABASE_ID=<Database ID>
```

## 今後の対応

- 日次スケジュール実行への組み込み
- 本番運用時の監視・ログ管理
- Notion 内での記事管理ルールの整備
