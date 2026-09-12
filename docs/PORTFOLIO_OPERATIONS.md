# Portfolio公開運用手順

この文書は、`tech_article_nortification` の作業記録を
`tj-999-comp/sandbox-pages` へ公開するときの判断基準、実行手順、停止手順を定める。
公開処理は生成元と公開先にまたがるため、片側の確認だけで運用状態を変更しない。

## 現在の運用状態

- source registry の `tech_article_nortification` は `enabled: true` である。
- GitHub Actions の `request-publish.yml` は、mainへの作業記録pushで自動公開要求し、手動の固定SHA・対象basename指定も受け付ける。
- 作業記録の通常追加では metadata の `publish: true` を使い、mainへのpush後に公開・Slack通知まで行う。下書き・非公開の場合だけ `publish: false` にする。
- 複数recordを含むpushはrecordごとにdispatchし、sandbox-pagesのPages反映成功後にSlack通知する。

自動workflowは `enabled` や `publish` を変更しない。公開停止が必要な場合はsandbox-pages側のregistryと受入workflowを停止する。

## E2E・受入の確認状況

Issue 009に記録された2026-08-28の手動E2Eでは、受入、apply、Pages build/deploy、公開URL確認、Slack通知が成功し、no-op経路も確認済みである。

- sandbox-pages受入workflow run: `33158737917`
- 最終適用commit: `57830bd0738998d2856711ddcdb8078844566199`
- publication ID: `accept-33158737917-1-tech_article_nortification-work_record_014`
- 現在のsource registry: `enabled: true`

この証跡は受入経路の完了確認に使う。`publish: true` が標準であり、`publish: false` にする場合は非公開理由をrecordごとに確認する。切替の実施状況はsandbox-pages側のregistryと人間reviewerの承認記録を正本とする。

## 公開要求の条件

次の全項目を確認し、確認者と日時をIssueまたは作業記録に残す。

- source registryのrepository、branch、source directory、metadata directory、destination directory、`a_rendered` が正しい。
- generator ID、ファイル種別、ファイル数・サイズ上限、安全validator、digest/provenance検査が確定している。
- `enabled: true` の受入と、既存成果物がない場合のno-op受入が成功している。
- 新規record 1件について、固定commitを指定した受入、Pages deploy、想定URL、必要な通知を人間が確認している。
- provenanceのsource SHA、対象basename、生成物のdigest、deploy結果が相互に一致している。
- 失敗時に停止し、監査可能な取り下げまたは再実行へ移れることを確認している。

対象record、固定commit、確認者を記録する。既存recordを一括公開しない。

## `publish: true` の扱い

1. Markdownとmetadataを同じcommitに含め、source-side validatorを実行する。
2. reviewerが内容、秘密情報の不存在、公開先URL、通知の要否を確認する。
3. metadataの `publish: true` と、同じcommitの40文字SHA、basenameを記録する。
4. mainへpushして自動要求する。再公開・復旧時は `request-publish.yml` を起動し、入力は `source_commit_sha` と `target_basename` の2入力だけにする。
5. sandbox-pagesの受入結果、Pages URL、provenance、通知結果を確認する。

公開要求workflowが対象record以外を変更することは想定しない。受入失敗時は再送せず、失敗理由と固定SHAを確認してから新しい承認を得る。

## 通常の公開要求

生成元リポジトリで、公開対象を含む固定commitを用意する。

```bash
python3 scripts/validate_work_records.py
git diff --check
git status --short
```

そのcommitをmainへ反映すると、GitHub Actionsの `Request work-record publish` が変更recordを自動選択する。

```text
source_commit_sha: <対象commitの40文字SHA>
target_basename:   work_record_###
```

Actionsが指定SHAをcheckoutしてrecordを再検証し、成功した場合だけsandbox-pagesの受入workflowへdispatchする。dispatch認証は、`PUBLISH_APP_ID`と`PUBLISH_APP_PRIVATE_KEY`から`sandbox-pages`だけを対象とする短期GitHub App installation tokenを発行する。source側でsandbox-pagesをcheckout・編集・commit・pushしたり、Contents write tokenを使ったりしない。

source repositoryのActions Secretは次の名前を使う。

```text
PUBLISH_APP_ID
PUBLISH_APP_PRIVATE_KEY
```

App tokenはworkflow実行時に発行され、保存・ログ出力しない。旧 `SANDBOX_PAGES_DISPATCH_TOKEN` は使用しない。

## 緊急停止

異常な公開、想定外の対象、digest不一致、通知先の誤りを検知したら、次の順で停止する。

1. sandbox-pages側のsource registryを `enabled: false` に戻す。これはsandbox-pagesの管理者が行い、生成元workflowから直接変更しない。
2. 実行中の受入・apply・Pages deploy workflowを停止する。停止したrun IDと時刻を記録する。
3. 最後に正常だったsource commit、対象basename、provenance、生成物digest、Pages deploy結果を照合する。
4. 照合できない場合は再送・再有効化せず、driftとして扱ってレビューへ戻す。
5. 影響がある公開物は、sandbox-pagesの監査可能な取り下げworkflowで処理する。生成元で公開先ファイルを削除しない。

## 復旧、rollback、通知失敗

- 復旧は原因、最後の正常commit、provenanceの一致を確認してから行う。
- rollbackは「直前の正常な公開状態」へ戻す操作として扱い、未確認の再生成物を上書きしない。
- Slack通知だけが失敗した場合も、先にPagesとprovenanceが正常であることを確認する。通知だけを再送する場合は、同じpublication IDへの重複送信にならないことを確認してから行う。
- 受入、deploy、provenance、通知のどれかが不明な場合は、全体を未完了として停止する。
- digest driftを検知した場合は自動再送せず、source SHA・対象basename・期待digest・実digestを記録して再承認を待つ。

## 責任境界

| 領域 | 担当 | できること |
| --- | --- | --- |
| source記録 | 生成元maintainer | Markdown/metadataの作成、validator、固定SHAの提示 |
| 公開承認 | 人間reviewer | 対象1件、`publish: true`、通知要否の承認 |
| 受入・Pages | sandbox-pages operator | registry、acceptance、apply、deploy、provenance、停止・取り下げ |
| 定期通知 | GAS operator | Script Properties、時間主導trigger、dispatch結果の確認 |
| アプリ処理 | GitHub Actions | 指定されたworkflowの実行。公開先のContents writeは持たない |

source側から渡す公開要求入力は `project_id`、`source_commit_sha`、`target_basename` に限定する。token、Secret、Webhook URL、記事データをIssue、ログ、作業記録へ記録しない。

## 参照

- [source-side validator](../scripts/validate_work_records.py)
- [公開要求workflow](../.github/workflows/request-publish.yml)
- [sandbox-pages公開ルール](https://github.com/tj-999-comp/sandbox-pages/blob/main/projects/README.md)
- [Issue 009の手動E2E証跡](../Issues/Issue_009.md)
