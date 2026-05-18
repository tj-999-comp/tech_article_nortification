# Issue 007: Qiita取得ロジック改修と定期実行設定更新

## 背景
- 取得ロジック変更後に人気順が正しく反映されない懸念があり、取得・通知フローを見直した。
- あわせて GitHub Actions の定期実行時刻を運用方針に合わせて変更した。

## 実施内容
- Qiita取得を「過去7日」条件で全ページ収集し、`likes_count` 降順で並べるように改修。
- `QIITA_API_TOKEN` を利用した Bearer 認証を追加し、レート制限耐性を改善。
- ローカル実行時に `Qiita.txt` を自動読込するように変更。
- 取得件数と通知件数を分離。
  - 取得: 上位20件（検証用）
  - 通知/同期: 10件（運用用、`QIITA_NOTIFY_LIMIT` 既定値）
- Slack投稿ペイロードを分割し、長文時の `invalid_blocks` エラーを回避。

## スケジュール設定
- 対象: `.github/workflows/daily-qiita-notify.yml`
- 定期実行:
  - 水曜 08:00 JST
  - 土曜 08:00 JST
- テスト用一時 cron:
  - 2026-05-18 13:00 JST 向けエントリを追加し、`workflow_dispatch` でも起動確認を実施。

## 動作確認
- ローカル手動実行で Step1〜Step3 成功を確認。
- Step4（Notion同期）も実行成功を確認。
- GitHub Actions は手動起動イベントを発火し、実行を確認。

## 補足
- テスト用一時 cron は検証完了後に削除予定。
