# Issue 000: 初期実装の変更記録

この変更では、小さな通知アプリを追加し、Qiitaの直近人気記事上位5件を取得して、各記事本文から短い要約を生成し、Slackへ送信し、後で読む・評価するためにNotionへリンクを保存できるようにしました。

## 変更内容

- 通知フロー
  - 単一ファイルのPythonアプリを追加し、以下を実装:
    - Qiitaから高いいね記事を取得
    - 記事データを小さな内部モデルへ正規化
    - タイトルと本文から約100文字の要約を生成
    - 上位5件をSlackメッセージのペイロードに整形

- Notionへの保存
  - 記事ごとにNotionデータベースへ1行作成する連携を追加
  - 既存の`URL`を確認し、重複登録をスキップ
  - 後追いレビュー向けの管理プロパティを初期化・保存:
    - `Read`
    - `Read Date`
    - `Helpful`
    - `Read Again`
    - そのほか、タイトル・要約・著者・タグ・公開日時・通知日時などのメタデータ

- 運用対応
  - 毎日実行するGitHub Actionsのスケジュールワークフローを追加
  - Slack・Notion・Qiita検索設定をリポジトリのSecrets/Variablesから注入
  - ワークフロートークン権限を、リポジトリ内容の読み取り専用に制限

- リポジトリドキュメント
  - READMEを拡張し、以下を追記:
    - 必須環境変数
    - 想定するNotionデータベーススキーマ
    - ローカル実行方法とドライラン手順

- 焦点を絞ったテスト
  - 次の観点に限定したユニットテストを追加:
    - 要約生成
    - Qiitaクエリ構築
    - Slackペイロード構造
    - Notionペイロード生成と重複検知

## 主要処理の例

```python
articles = fetch_qiita_trending_articles(lookback_days=7, limit=5)
payload = build_slack_payload(articles)
post_to_slack(slack_webhook_url, payload)
save_articles_to_notion(
    articles,
    notion_token=notion_token,
    database_id=notion_database_id,
)
```

## 警告

> [!WARNING]
>
> <details>
> <summary>ファイアウォールルールにより、一部アドレスへの接続がブロックされました（クリックで詳細表示）</summary>
>
> #### 接続を試みたものの、ファイアウォールによりブロックされたアドレス:
>
> - `qiita.com`
>   - 発生コマンド: `/home/REDACTED/work/_temp/ghcca-node/node/bin/node /home/REDACTED/work/_temp/ghcca-node/node/bin/node --enable-source-maps /home/REDACTED/work/_temp/copilot-developer-action-main/dist/index.js`（DNSブロック）
>   - 発生コマンド: `/usr/bin/python python -`（DNSブロック）
>
> これらの場所へのアクセス・ダウンロード・インストールが必要な場合は、次のいずれかを実施してください。
>
> - ファイアウォール有効化前に実行される [Actions setup steps](https://gh.io/copilot/actions-setup-steps) を構成する
> - このリポジトリの [Copilot coding agent settings](https://github.com/tj-999-comp/tech_article_nortification/settings/copilot/coding_agent) で、必要なURLまたはホストをカスタム許可リストに追加する（管理者のみ）
>
> </details>

## 元プロンプト（記録）

- Web記事をSlackに通知するアプリケーションを作成する。
- Qiita（https://qiita.com/）のトレンド人気記事5つを毎日Slackで通知する。
- 見出しと内容から、紹介文を100字程度でまとめて見せる。
- そのリンクはNotionのDBに蓄積させる。
- 読んだかどうか、読んだ日はいつか、役に立ったかどうか、繰り返し読みたいか、などをNotionで管理する。
