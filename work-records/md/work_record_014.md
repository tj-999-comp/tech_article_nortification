# 作業記録 014: Issue #9の手動公開E2E候補

作成日: 2026-08-28

## 概要

`tech_article_nortification` の作業記録公開契約を、実データ1件で手動確認するための公開候補。source側で固定commitと対象basenameを検証し、`sandbox-pages` の受入、`a_rendered`生成、GitHub Pages公開、公開URL、provenance、通知までを確認する。

## 確認対象

- `project_id`: `tech_article_nortification`
- `html_mode`: `a_rendered`
- 対象basename: `work_record_014`
- 受入入力: 検証済みsource commitのSHAと対象basename

## 安全境界

この記録にはtoken、Webhook URL、個人情報、記事本文を含めない。公開先のファイルとprovenanceは`sandbox-pages`側の受入workflowだけが生成・管理し、source側から公開リポジトリを編集しない。

## 目的

公開要求が固定入力だけを受け取り、sourceのMarkdownとmetadataを受入側で再検証したうえで、想定URLと来歴情報を生成できることを人間確認する。
