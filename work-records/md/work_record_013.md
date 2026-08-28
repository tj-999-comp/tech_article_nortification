# 作業記録 013: Issue #5の公開受入契約とsource-side検証
作成日: 2026-08-28

## 概要

Issue #5「Portfolio: generator ID・ファイル上限・受入workflow契約を確定」に対応し、生成元から受入側へ渡す作業記録の入力契約と、公開前に実行するsource-side検証を整備した。

## 対応内容

- 固定契約を文書化
  - `project_id`: `tech_article_nortification`
  - 公開方式: `a_rendered`
  - 対象: `work-records/md/work_record_###.md`と対応するmetadata
  - 公開要求入力: `project_id`、検証済み`source_commit_sha`、`target_basename`
- 依存パッケージなしのvalidatorを追加
  - basenameとMarkdown/metadataの対応
  - metadata schema、日付、タグ、project_id、`publish`
  - UTF-8、symlink、NUL、危険なURL scheme、protocol-relative link
- read-onlyのGitHub Actions検証workflowを追加
  - mainへのpush、Pull Request、手動起動に限定
  - `contents: read`のみを付与し、Secret・公開側write権限・外部通知を持たせない
- 既存の作業記録001〜012を共通構成へ揃え、reviewableなmetadataと回帰fixtureを用意

## 受入側との対応

受入リポジトリ`sandbox-pages`のsource registryで、generator ID、ファイル数・単体サイズ・合計サイズ上限、`workflow_dispatch`の3入力が固定されていることを照合した。A所有の`a_rendered` rendererはIssue #13 / PR #57でmainへ反映済みであり、generator IDからの一意解決条件も満たした。生成元側の公開要求workflow、disabled dry-run、実データによる手動E2E、sourceの有効化は後続Issue #8以降へ引き継ぎ、sourceは`enabled: false`のまま維持する。

## 検証結果

- `python3 -m unittest discover -s tests -v`: 25件成功
- `python3 scripts/validate_work_records.py --require-publish-false`: 13件成功
- `sandbox-pages`: `python3 -m unittest discover -s tests -v`: 79件成功
- `PYTHONPYCACHEPREFIX=/tmp/tech_article_nortification_pycache python3 -m py_compile scripts/validate_work_records.py tests/test_validate_work_records.py`: 成功
- `git diff --check`: 成功

## GitHub Issue状況

確認日時（JST）: 2026-08-28

| GitHub Issue | 状態 | 関係 |
| --- | --- | --- |
| [tech_article_nortification #5](https://github.com/tj-999-comp/tech_article_nortification/issues/5) | Closed | 本作業の対象。契約確定、source-side検証、受入側rendererとの整合確認を完了し、Issue #8以降へ引き継いだ。 |
| [sandbox-pages #13](https://github.com/tj-999-comp/sandbox-pages/issues/13) | Closed | A所有の`a_rendered` renderer。PR #57、merge commit `4154548c280c452187e9039ba2a3aa9f3ecb9e85`で完了。 |

## 未解決事項

- 生成元側の公開要求workflow（Issue #8）
- disabled dry-run、手動E2E、受入後の`enabled`切替
- GitHub Actions上での実公開確認

Secret、token、Webhook URLは記録していない。
