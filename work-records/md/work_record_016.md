# 作業記録 016: GASのGitHub認証復旧

作成日: 2026-08-30

## 概要

GASからGitHub Actionsを定期起動する経路で発生していた認証エラーを確認し、GitHub Personal Access Tokenを再発行してGASのScript Propertiesを更新した。更新後の手動実行は成功したため、GASからGitHub Actionsへのdispatch経路は復旧したと判断する。自動実行の確認は次回に持ち越す。

## 発生していたエラー

- 発生日時: 2026-08-29 07:47:26
- 発生箇所: GASの`myFunction`
- エラー: GitHub APIへのリクエストがHTTP 401で失敗（`Bad credentials`）
- エラー内容から、期限切れに限らず、GASから送信されたトークンがGitHubで認証情報として受理されていない状態と判断した。

## 対応

- GitHubのPersonal Access Tokenを再発行した。
- GASのScript Propertiesに登録している`GITHUB_TOKEN`を新しいトークンへ更新した。
- トークン更新後、GASからGitHub Actionsのworkflowを手動実行した。

## 結果

- 手動実行は成功した。
- GASからGitHub Actionsへのworkflow dispatchが成功することを確認した。
- 今回の手動実行により、Actionsのパイプラインが実行され、Slack投稿・Notion登録まで行われる構成であることを確認した。

## 補足調査

- エラー履歴の関数名は`myFunction`だったが、リポジトリの現行GASコードでは`triggerGitHubWorkflow`を使用している。
- エラーメッセージの形式も現行コードのエラー処理とは異なるため、GAS側にはリポジトリより古いコードが残っている可能性がある。
- GASの`GITHUB_TOKEN`はGitHub ActionsのリポジトリシークレットやActions実行時に自動生成される`GITHUB_TOKEN`とは別の、GAS Script Propertiesに保存する認証情報である。

## 次回確認

1. GASのトリガー一覧で`runScheduledWorkflow`が水曜・土曜08:00（`Asia/Tokyo`）として登録されているか確認する。
2. 同じ関数のトリガーが重複していないか確認する。
3. 次回の自動実行後、Apps Scriptの実行履歴が成功しているか確認する。
4. GitHub Actionsに`workflow_dispatch`の実行が作成され、`Run pipeline`が成功しているか確認する。
5. Slack投稿とNotion登録が重複せず、1回だけ実行されたか確認する。

自動実行のテストを追加で行う場合も、実データによるSlack投稿とNotion登録を伴うため、複数のテストトリガーを同時に設定しない。

## 安全境界

この記録にはトークン、Webhook URL、個人情報、記事本文を含めない。トークン値は記録・共有しない。自動実行の確認が完了するまでは公開対象にしない。
