# 作業記録 011: Issue #2のsandbox-pages公開連携タスク分解
作成日: 2026-08-27

## 概要

生成元リポジトリからsandbox-pagesへwork-recordを安全に公開するためのGitHub Issue #2を、実装・検証・運用判断の単位に分解した。

## 適用した役割

### 実際に担当したRole

- 公開連携タスクの分析
- GitHub Issueの子Issue設計
- 受入条件と安全境界の整理

## 主要な判断

- sandbox-pagesの公開ルール正本を確認し、source registry、renderer、受入検証、公開要求、手動E2E、運用切替を分離した。
- 新しい生成元は`a_rendered`方式を使い、HTML・CSSを生成元リポジトリで管理しない前提を子Issueへ反映した。
- 公開先のwrite権限やtokenを生成元へ渡さず、公開要求の入力を`project_id`、固定した`source_commit_sha`、`target_basename`の3つに限定する方針を維持した。
- `enabled: true`と`publish: true`の判断を、受入検証と人間確認付きの手動E2Eが完了した後の最終工程へ分離した。

## 作成した子Issue

Issue #2に次の7件を作成し、親Issue本文へ依存順のチェックリストを追加した。

1. [#4 source registryへの登録](https://github.com/tj-999-comp/tech_article_nortification/issues/4)
2. [#5 generator ID・ファイル上限・受入workflow契約](https://github.com/tj-999-comp/tech_article_nortification/issues/5)
3. [#6 `a_rendered` renderer・安全validator・digest検証](https://github.com/tj-999-comp/tech_article_nortification/issues/6)
4. [#7 dry-run・no-op受入・provenance drift検証](https://github.com/tj-999-comp/tech_article_nortification/issues/7)
5. [#8 固定commit・basename限定の公開要求workflow](https://github.com/tj-999-comp/tech_article_nortification/issues/8)
6. [#9 新規1件の手動E2E](https://github.com/tj-999-comp/tech_article_nortification/issues/9)
7. [#10 E2E完了後のenabled・publish運用切替](https://github.com/tj-999-comp/tech_article_nortification/issues/10)

## 依存関係

```text
#4 ─┐
    ├→ #6 ─┐
#5 ─┤      ├→ #9 → #10
    ├→ #7 ─┤
    └→ #8 ─┘
```

- #4・#5でsource registryと受入契約を確定する。
- #6・#7・#8でrenderer、受入検証、公開要求経路を整える。
- #9で新規1件の受入、Pages deploy、公開URL、必要な通知を人間確認する。
- #10で確認結果をもとに有効化と運用引き継ぎを判断する。

## 確認結果

- Issue #2は公開連携全体を追跡する親Issueとして維持した。
- 子Issueはすべて作成済みで、親Issue本文から参照できる。
- GitHubの正式なSub-issues APIによる親子設定はこのリポジトリでは利用できなかったため、親Issueのチェックリストで関係を明示した。
- ソース側のコード・workflow・metadataは変更していない。
- 子Issue本文および本作業記録にtoken、Secret、Webhook URL、記事データは記録していない。

## 次の予定

- #4、#5から順に着手し、受入契約とA所有renderer・validatorの実装範囲を確定する。
- 手動E2Eと人間確認が完了するまで、公開連携を有効化しない。
