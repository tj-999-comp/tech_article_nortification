# Issue 002: 記事情報のローカル保存（articles配下）対応

## 背景

次フェーズ（要約改善・Slack通知拡張）に進む前に、まずQiitaから取得した記事情報をローカルへ確実に保存できるようにする必要があった。

## 対応内容

- [app.py](../app.py) に記事スナップショット保存処理を追加
  - `save_articles_snapshot` を追加
  - 保存先ディレクトリを `articles` に固定（引数で上書き可能）
  - 保存ファイル名を `YYYYMMDD.json` 形式で生成
  - 保存内容に以下を含める
    - `fetched_at`
    - `count`
    - `articles`（title/url/summary/author/likes/published_at/tags）

- 既存モデルの拡張
  - `Article` に `likes` フィールドを追加
  - Qiitaレスポンスの `likes_count` を `likes` として取り込み

- 実行フローへの組み込み
  - `main()` 内でQiita取得直後に `save_articles_snapshot(articles)` を実行

- テスト追加・更新
  - [tests/test_app.py](../tests/test_app.py)
    - `likes_count` 取り込みの検証を追加
    - `save_articles_snapshot` が `articles/YYYYMMDD.json` を出力することを検証
    - 保存JSONの件数と記事項目（likes/title）を検証

- ドキュメント更新
  - [README.md](../README.md) に「取得記事を `articles/YYYYMMDD.json` に保存」を追記

## 確認結果

- テスト実行コマンド: `python3 -m unittest discover -s tests -v`
- 結果: 8件実行、すべて成功

## 影響範囲

- 変更ファイル
  - [app.py](../app.py)
  - [tests/test_app.py](../tests/test_app.py)
  - [README.md](../README.md)
  - [Issues/Issue_002.md](./Issue_002.md)

## 次の予定

- Step 2: 要点の100字要約ロジックを改善
- Step 3: Slack通知フォーマットと通知導線の強化
