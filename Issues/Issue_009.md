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

## 現行構成（2026-08-29更新）

- `.github/workflows/daily-qiita-notify.yml` は削除せず、`workflow_dispatch` 専用として維持する。
- 定期起動は `gas/trigger_github_workflow.gs` の `runScheduledWorkflow` が担当し、水曜・土曜の08:00（`Asia/Tokyo`）にGitHub Actionsをdispatchする。
- GitHub Actions側に `schedule` は設定しない。これにより、GASとActionsの二重起動を防ぐ。
- 2026-08-29の確認時点で、通知workflowの最後の実行は2026-05-29だった。以降のSlack未更新は、GASトリガー未実行またはGASからのdispatch失敗が第一候補である。
- GASの実行履歴、時間主導トリガー、Script Properties（`GITHUB_TOKEN`）は、Apps Script側で確認する必要がある。

## 追記: GitHub Issue #9 手動公開E2E

2026-08-28 に、Sandbox Pages への新規作業記録公開E2Eを実施した。

### 対応内容

- `work-records/md/work_record_014.md` と対応metadataを追加した。
- metadataの `title` を引用付きYAMLとして修正し、A側の通常validatorで受入可能な状態にした。
- A側のvalidatorは通常実行で通過し、Issue #9用の明示的な `publish: true` 候補を検証した。
- Sandbox側の受入workflowは、A側validatorが返す `changed_paths` を個別にforce-stageするよう修正した。これにより、生成HTML/Markdownを公開コミットへ確実に含める。

### 証跡

- A側source commit: `8213927aa71770355941f133c7bac60f58e7d04b`
- A側変更PR: #14（record追加・validator調整）、#15（metadata title修正）
- Sandbox側staging修正PR: #67、#68
- 最終受入E2E: `sandbox-pages` workflow run `33158737917`
- 最終適用commit: `57830bd0738998d2856711ddcdb8078844566199`
- publication ID: `accept-33158737917-1-tech_article_nortification-work_record_014`
- 受入、適用、Pages build/deploy、公開URL確認、Slack通知の全ジョブが成功した。

### 公開確認

- [work_record_014 公開ページ](https://tj-999-comp.github.io/sandbox-pages/projects/tech_article_nortification/work_record_014.html)
- project indexから `./work_record_014.html` の相対リンクを確認した。
- global indexから `./tech_article_nortification/work_record_014.html` の相対リンクを確認した。
- provenanceにはsource SHA、公開ファイルのSHA256、`notify: true` が記録されている。
- Markdown原本リンク `md/work_record_014.md` の存在を確認した。

### 後処理・制約

- E2E後、Sandbox側source registryは `enabled: false` に戻した（cleanup PR #69）。公開済みrecordとprovenanceは保持している。
- A側からSandboxへdispatchする経路は、必要なdispatch secretが未設定のためrun `33151188926` がfail-closedとなった。secretの値は記録・変更していない。最終E2Eは明示的なworkflow dispatchで完了した。
- 作業記録にはtoken、webhook、個人情報などの秘密情報を含めていない。
