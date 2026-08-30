# 作業記録 017: GitHub Models終了に伴う通知workflow復旧

作成日: 2026-08-30

## 概要

GASの時間主導トリガーからGitHub Actionsへのdispatchは成功していたが、ActionsのStep2で要約処理が停止してSlack・Notionまで到達していないことを確認した。原因は、終了済みのGitHub Models APIを定期通知workflowが必須利用していたことだった。定期通知を継続できるよう、ルールベース要約を本番経路に切り替えた。

## 調査結果

- GASの実行後、GitHub Actionsに`workflow_dispatch`の実行が作成されていた。
- Step1のQiita記事取得は成功し、`articles/raw_20260830.json`が生成されていた。
- Step2のLLM要約で`models.inference.ai.azure.com`の名前解決に失敗した。
- 失敗した実行ではStep3のSlack通知とStep4のNotion同期は実行されていない。
- GitHub Modelsは2026-07-30に終了しており、旧エンドポイントの復旧利用はできない。

## 対応

- GitHub Actionsの定期通知workflowに`SUMMARIZER_MODE=rule`を設定した。
- `REQUIRE_LLM_SUCCESS=false`に変更し、要約API障害で後続処理を停止しない設定にした。
- workflowから不要になった`GHUB_MODELS_API_KEY`の注入を削除した。
- アプリケーションの要約既定値をルールベースに変更した。
- 旧GitHub Modelsエンドポイントを既定値から削除し、明示指定がない場合は廃止済みであることを示すエラーにした。
- READMEとAGENTS.mdの運用説明を現行構成に合わせた。

## 検証

- `PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py' -v`: 29件成功
- `python3 scripts/validate_work_records.py`: 16件成功（この記録追加前）
- `git diff --cached --check`: 成功
- `git diff --check`: 成功
- 実データを使う修正後のActions手動実行は、Slack・Notionの重複投稿を避けるためこの作業では行っていない。

## 次回確認

1. 次回のGAS自動dispatchでActionsの`workflow_dispatch`実行が作成されることを確認する。
2. Step1からStep4まで成功し、Slack・Notionに1回だけ反映されることを確認する。
3. ルールベース要約の内容が運用上許容できるか確認する。
4. LLM要約を再導入する場合は、GitHub Models以外の現行サービスと専用Secretを別途選定する。

## 安全境界

この記録にはtoken、Webhook URL、個人情報、記事本文を含めない。GitHub ActionsのSecret値はログに出力していない。実データを送信するworkflowの再実行は、重複投稿の確認方針を決めてから行う。
