# 作業記録 015: GAS定期実行とSlack未更新の調査

作成日: 2026-08-30

## 概要

Qiita記事通知アプリの実装・GAS運用に合わせてドキュメントを整理し、Slack通知が更新されていない原因を調査した。今回の作業ではSlack通知の復旧までは行わず、次回セッションでApps Script側を確認・復旧するための調査結果を引き継ぐ。

## ドキュメント整理

- READMEの目的を、Qiita APIから過去7日間の記事を最大20件取得し、最大10件をSlack通知・Notion同期する構成に統一した。
- 実行順を `Step1 → Step2 → Step3 Slack → Step4 Notion` と明記した。
- 定期起動をGASの水曜・土曜08:00（Asia/Tokyo）トリガー、GitHub Actionsを `workflow_dispatch` 専用として整理した。
- LLM要約失敗時の `REQUIRE_LLM_SUCCESS` による挙動と、Notionの `Read Date` が現状未使用であることを追記した。
- AGENTS.mdとIssue 009の記載を、現在のGAS・Python実装・workflowに合わせた。

## Slack未更新の調査結果

- 現在の `.github/workflows/daily-qiita-notify.yml` に `schedule` はなく、定期起動はGASからのGitHub API dispatchに依存している。
- GitHub Actionsの通知workflowの最後の実行は、2026-05-29の成功した `schedule` 実行だった。
- 2026-08-29の確認時点で、現在のworkflowを対象とした新しい実行は確認できなかった。
- そのため、第一候補はGASの時間主導トリガーが停止・未登録であること、またはGASからのdispatch失敗である。
- GASのdispatch先workflowがmainに戻る前は存在しなかったため、2026-08-29朝のdispatchが実行されていた場合は404になった可能性がある。現行workflowは同日後にmainへ反映された。
- Apps Scriptの実行履歴、トリガー、Script Propertiesの `GITHUB_TOKEN` はリポジトリから確認できないため、次回はApps Script側で確認する。

## 検証

- `PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py' -v`: 27件成功
- `python3 scripts/validate_work_records.py`: 14件成功
- `git diff --check`: 成功

## 次回対応

1. Apps Scriptの実行履歴で `runScheduledWorkflow` の最終実行結果を確認する。
2. 時間主導トリガーが水曜・土曜08:00（Asia/Tokyo）で登録されているか確認する。
3. Script Propertiesの `GITHUB_TOKEN`、`GITHUB_REPOSITORY`、`GITHUB_WORKFLOW`、`GITHUB_REF` を確認する。token値は記録しない。
4. `triggerGitHubWorkflow` を手動実行し、HTTP 204が返るか確認する。
5. Actionsの `Run pipeline` が起動した後、必要に応じてQiita・GitHub Models・Slack・Notionの失敗箇所を確認する。

## 安全境界

この記録にはtoken、Webhook URL、個人情報、記事本文を含めない。Slack復旧のための手動workflow実行は、実際のSlack投稿とNotion更新を伴うため、確認内容を決めてから実施する。
