"""GitHub Models API の手動テスト用スクリプト"""
import os
import app

title = "DockerとKubernetesで始めるコンテナ運用入門"
body = """
# はじめに

コンテナ技術は現代のインフラ運用に欠かせない要素となっています。

# Dockerとは

Dockerはアプリケーションをコンテナとして梱包・実行するプラットフォームです。
仮想マシンと比べ起動が速く、環境差異が生まれにくいメリットがあります。
主な用途は開発環境の統一、CI/CDパイプラインの構築、本番デプロイです。

# Kubernetesとは

Kubernetesはコンテナのオーケストレーションシステムです。
複数のコンテナを自動スケールし、障害発生時に自動で再起動する機能を持ちます。
Google発のOSSで、現在はCNCFが管理しています。

# 本番運用での注意点

リソースのlimits/requestsを必ず設定すること。
Probeの設定（liveness/readiness）を忘れずに実装すること。
セキュリティポリシーはPodSecurityAdmissionで管理することを推奨します。

# まとめ

DockerとKubernetesを組み合わせることで、可用性が高く運用コストの低いシステムを構築できます。
"""

print("=== テスト開始 ===")
print(f"タイトル: {title}")
print(f"SUMMARIZER_MODE: {os.getenv('SUMMARIZER_MODE')}")
print(f"API KEY 設定済み: {'yes' if os.getenv('GITHUB_MODELS_API_KEY') else 'no'}")
print()

# ルールベース要約
rule_summary = app.summarize_article_rule_based(title, body)
print(f"[ルールベース要約] ({len(rule_summary)}字)")
print(rule_summary)
print()

# LLM要約
try:
    llm_summary = app.summarize_article_with_github_models(title, body)
    print(f"[LLM要約] ({len(llm_summary)}字)")
    print(llm_summary)
    print()
    print("=== API呼び出し: 成功 ===")
except RuntimeError as e:
    print(f"[LLM要約] エラー: {e}")
    print("=== API呼び出し: 失敗 → フォールバック ===")

# summarize_article 統合
final = app.summarize_article(title, body)
print()
print(f"[最終出力 (mode={os.getenv('SUMMARIZER_MODE', 'rule')})] ({len(final)}字)")
print(final)
