# 作業記録テンプレート

このテンプレートは、`tj-999-comp/sandbox-pages` の2026-09-07時点の
`PORTFOLIO_STANDARD.md` と `work-records/README.md` に合わせた、
`tech_article_nortification` 用のMarkdown作業記録形式である。

このリポジトリは `a_rendered` 方式のため、公開payloadである
`work-records/md/` と `work-records/metadata/` の外へテンプレートファイルを
置かない。テンプレートはこの文書で管理し、作業記録のMarkdownは必ず
`work-records/md/work_record_###.md`へ作成する。

## Markdownテンプレート

````md
# 作業記録 ###: <内容>
作成日: YYYY-MM-DD

## 概要
- 課題:
- 目的:
- 完了条件:

## 適用した役割
### 実際に担当したRole
- 入力:
- 実施内容:
- 成果物:
- 検証結果:
- 未解決事項:
- 次工程への引き継ぎ:

## 主要な判断
- 判断:
- 理由:

## 最終結果
- 解決したこと:
- 変更ファイル:
- 検証結果:
- 作業ブランチ:
- コミット:
- PR:
- PRレビュー・CI:
- 未解決事項:
- 次アクション:

## GitHub Issue状況
確認日時（JST）: YYYY-MM-DD HH:MM
取得範囲: <このリポジトリの全Open Issue。Pull Request除外>
取得件数: <Open Issue件数>（一覧行数: <表のIssue行数>）

### 親子関係
```text
<確認できた親子関係、または親子関係なし>
```

### 優先順位順の未完了一覧
| 順位 | 優先度 | GitHub Issue | 状態 | 関係・着手条件 |
| ---: | --- | --- | --- | --- |
| 1 | P0 | [#<番号> <タイトル>](https://github.com/owner/repository/issues/<番号>) | 未完了（state reason: null） | <関係・着手条件> |
````

Issue状況は作業記録ごとに取得する。GitHubへ接続できない場合は状態を推測せず、取得不可の理由と未確認範囲を記録する。実際に担当していないRole欄は作成しない。

## metadataテンプレート

`work-records/metadata/work_record_###.yml`には、次の6キーだけを記載する。

````yaml
schema_version: 1
title: "<Markdownのタイトルと一致する内容>"
date: "YYYY-MM-DD"
project_id: tech_article_nortification
tags:
  - <tag>
publish: true
````

このテンプレートのデフォルトは `publish: true` とする。作業記録をmainへpushした際に公開・Slack通知まで行うためである。下書き・非公開にしたい場合だけ、内容確認時に明示的に `publish: false` へ変更する。

## 検証

```bash
python3 scripts/validate_work_records.py
git diff --check
```

公開要求workflowは、生成元のmain更新時に変更された `publish: true` のrecordを自動検出する。手動起動では `source_commit_sha` と `target_basename` の2入力だけを指定する。`project_id`、公開先repository、受入workflowはこのリポジトリの固定設定から決定する。
