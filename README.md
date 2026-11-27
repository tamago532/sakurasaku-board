# サクラサク相談室

高校生向けの、進路・受験・就活の匿名相談掲示板です。

- サイト：（公開後に記入）
- 要件定義：[requirements.md](requirements.md)

## 主な機能

- 相談の投稿・返信（受験方式・分野で絞り込み、新着順／わかる順）
- 「わかる」ボタン、解決済みマーク、あいことばによる削除
- 卒業生の投稿に先輩バッジ
- 電話番号・メールアドレス・SNSのID・悪口の自動ブロック
- 相談・返信への画像添付
- 共通テスト（2027年1月16日 9:30）までのリアルタイムカウントダウン

## 構成

| 役割 | 使ったもの |
| --- | --- |
| Web アプリ | Python / Flask（Azure App Service） |
| 投稿の保存 | Azure Table Storage |
| 画像の保存 | Azure Blob Storage |
| 自動公開 | GitHub Actions |
| ストレージへの接続 | Managed Identity（接続文字列やキーは使わない） |

## ローカルで動かす

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
```

環境変数 `AZURE_STORAGE_ACCOUNT_NAME` が無いときは、`local_data/` に保存して動きます。
