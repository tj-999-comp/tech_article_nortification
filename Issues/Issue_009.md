# Issue 009: GitHub Actions 定期通知の無効化

作成日: 2026-06-02

## 概要
GAS の時間主導トリガーと GitHub Actions の定期実行が重なり、同じ日に Slack 通知が 2 回送信される状態になっていたため、GitHub Actions 側の自動実行を無効化した。

## 背景
- 木曜・土曜の朝に、7:30 前後と 8:30 前後で通知が 2 回届くことを確認した。
- 実行履歴を確認したところ、GAS 経由の workflow_dispatch と GitHub Actions の schedule が同日に別々に走っていた。
- 通知処理自体には同日重複を防ぐ仕組みがなかったため、起動元を整理する方針とした。

## 実施内容
- .github/workflows/daily-qiita-notify.yml を .disabled へリネームして GitHub Actions の自動実行を停止した。
- 変更を main ブランチへ push した。

## 確認結果
- GitHub Actions の schedule / workflow_dispatch による自動起動は、対象 workflow ファイルが存在しないため無効化された。
- 今後は GAS 側のトリガーのみで通知を実行する。

## 今後のメモ
- 必要であれば、GAS 側にも重複防止のガードを追加する。
- 将来的に GitHub Actions を再開する場合は、GAS トリガーとの役割分担を再整理する。