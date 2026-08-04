# 前原誠司 サイト（リニューアル版）

公式サイト（maehara21.com）のホーム・プロフィール・政策ページをスクレイピングして
SQLiteに格納し、Streamlitで再構築したサイトです。

## 構成

```
scraper/scrape.py   公式サイトを取得し、テキスト・画像を data/ に保存するスクリプト
common/db.py         SQLiteスキーマ + 読み書きヘルパー（scraperとappで共有）
app/main.py           Streamlitエントリポイント（ナビゲーション・共通レイアウト）
app/views/            ホーム／プロフィール／政策 各ページ
app/theme.py           デザインシステム（CSS・共通コンポーネント）
app/assets/            スクレイピング対象外の独自素材（叡山電鉄の写真など）
data/                  scraperの出力（SQLite DB + 画像）。git管理下、再実行で上書きされる
```

## ローカルで動かす

```bash
python3 -m pip install -r requirements.txt

# 公式サイトから最新情報を取得してDBを構築（初回・更新時に実行）
python3 -m scraper.scrape

# アプリを起動
streamlit run app/main.py
```

`http://localhost:8501` で確認できます。

## Dockerで動かす

```bash
docker compose up --build
```

（`data/` はホストと共有されるので、事前に `python -m scraper.scrape` を実行してから
起動するか、コンテナ内で再度スクレイパーを実行してください。）

Cloud Run 等にデプロイする場合は `Dockerfile` をそのままビルドしてください。
`$PORT` 環境変数を読むようになっています。

## アクセスにパスワードをかける

環境変数 `SITE_PASSWORD` を設定すると、簡易パスワードゲートが有効になります
（本番用の認証ではなく、プレビュー共有用の簡易ロックです）。

```bash
SITE_PASSWORD=xxxx streamlit run app/main.py
```
