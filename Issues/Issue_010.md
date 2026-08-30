# Issue 010: E2E後の公開運用切替と引き継ぎ

## 対応状況

Issue #10の生成元側対応として、公開運用の判断基準と停止・復旧手順を
[Portfolio公開運用手順](../docs/PORTFOLIO_OPERATIONS.md) に整理した。

## 実施内容

- `enabled: true` に変更するための受入、E2E、provenance確認条件を明文化
- `publish: true` を承認済みの単一recordに限定する手順を明文化
- 固定commit SHA、`project_id`、対象basenameだけを使う公開要求手順を整理
- 緊急停止、実行中workflow停止、rollback、通知失敗時の再送条件、digest drift時の停止を整理
- source maintainer、reviewer、sandbox-pages operator、GAS operator、GitHub Actionsの責任境界を明文化
- bootstrapで既存10件を無条件に公開・通知しないことを明記
- READMEから運用手順へ導線を追加し、必須項目の回帰テストを追加

## 確認済みの証跡

- Issue 009に記録された手動E2Eで、受入、Pages deploy、公開URL確認、Slack通知が成功
- sandbox-pages受入workflow run: `33158737917`
- publication ID: `accept-33158737917-1-tech_article_nortification-work_record_014`
- E2E後のsource registryは `enabled: false` に戻されている
- source-side validator: 16件成功
- 回帰テスト: 29件成功

## 保留事項

- `enabled: true` への恒久切替は、人間reviewerの明示的な承認後にsandbox-pages側で実施する。
- 次のrecordを `publish: true` にする場合も、対象1件・固定commit・承認記録を用意してから手動実行する。
- source側からsandbox-pagesのregistry、Secret、Contentsを変更しない。

## 安全境界

token、Secret、Webhook URL、記事本文はこの記録へ含めない。既存の作業記録metadataや未承認の公開状態は、このIssue対応だけを理由に変更しない。
