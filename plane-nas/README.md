# Plane CE セットアップ手順 (UGREEN DXP4800 Plus)

Plane Community Edition v1.2.3 を NAS にデプロイする手順書。

## 前提条件

| 項目 | 値 |
|------|-----|
| NAS | UGREEN DXP4800 Plus |
| Plane バージョン | v1.2.3 (Community Edition, AGPL-3.0) |
| 要件 | 2 CPU コア, 4GB RAM, ディスク ~2GB |
| 外部ドメイン | plane.aloha-88.com |
| アクセス経路 | Cloudflare Tunnel + Tailscale |
| Proxy リッスンポート | 8082 (ホスト側) |

## 既存環境との共存

既存で稼働中のコンテナ: AdGuard Home, Stirling PDF, Vaultwarden, Duplicati, Baserow 等

- PostgreSQL・Redis(Valkey) は **Plane 専用コンテナ** として起動（既存DBと分離）
- コンテナ名にはすべて `plane-` プレフィックスを付与し衝突を防止
- ホスト側に公開するポートは **8082 番のみ**（proxy → Cloudflare Tunnel 経由）

---

## Step 1: ファイルを NAS に配置

NAS の Docker 管理ディレクトリにフォルダを作成し、以下のファイルを配置する。

```
/path/to/docker/plane-nas/
├── docker-compose.yml
├── .env
└── .env.example      # テンプレート (参考用)
```

```bash
# NASにSSH接続後
mkdir -p /path/to/docker/plane-nas
cd /path/to/docker/plane-nas
# 本リポジトリの plane-nas/ ディレクトリの内容をコピー
```

## Step 2: .env ファイルを確認・編集

`.env` にはシークレットキーやパスワードが事前生成済み。必要に応じて変更する。

```bash
# 新しいシークレットを生成したい場合
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

主な設定項目:

| 変数 | 説明 | デフォルト値 |
|------|------|-------------|
| `APP_DOMAIN` | Plane のドメイン | plane.aloha-88.com |
| `SECRET_KEY` | Django シークレットキー | (生成済み) |
| `POSTGRES_PASSWORD` | DB パスワード | (生成済み) |
| `RABBITMQ_PASSWORD` | MQ パスワード | (生成済み) |
| `LIVE_SERVER_SECRET_KEY` | Live サーバーキー | (生成済み) |
| `AWS_SECRET_ACCESS_KEY` | MinIO シークレット | (要変更) |

## Step 3: ポート競合確認

デプロイ前に、ホスト側のポート 8082 が他のコンテナに使われていないことを確認する。

```bash
# 使用中ポートの確認
docker ps --format "table {{.Names}}\t{{.Ports}}" | grep -E "8082|80:|443:"

# netstatでも確認
ss -tlnp | grep 8082
```

もし競合がある場合は `docker-compose.yml` の proxy サービスの `ports` を変更する:
```yaml
    ports:
      - "8083:80"  # 8082以外の空きポートに変更
```

## Step 4: デプロイ

```bash
cd /path/to/docker/plane-nas

# コンテナ起動
docker compose up -d

# 起動状況を確認
docker compose ps

# migratorが完了するまで待つ (exit 0 になればOK)
docker compose logs -f migrator
```

全コンテナが起動するまで 2-3 分かかる。migrator が正常終了後、API が利用可能になる。

### 起動確認

```bash
# APIヘルスチェック
curl -s http://localhost:8082 | head -20

# 全コンテナのステータス確認
docker compose ps
```

期待される状態:
- `plane-migrator`: Exited (0)
- その他すべて: Up (running)

## Step 5: Cloudflare Tunnel に plane.aloha-88.com を追加

1. [Cloudflare Zero Trust ダッシュボード](https://one.dash.cloudflare.com/) にログイン
2. **Networks** → **Tunnels** → 既存のトンネルを選択
3. **「Add a published application route」** ボタンをクリック
4. 以下を入力:

   | 項目 | 値 |
   |------|-----|
   | Subdomain | `plane` |
   | Domain | `aloha-88.com` |
   | Type | `HTTP` |
   | URL | `<NASのローカルIP>:8082` |

   例: URL = `http://192.168.1.xxx:8082`

5. 保存して、DNS が反映されるまで 1-2 分待つ

### 接続テスト

```bash
# ブラウザまたはcurlで確認
curl -I https://plane.aloha-88.com
```

## Step 6: 初期設定

### 6.1 管理者アカウント作成

1. ブラウザで `https://plane.aloha-88.com` にアクセス
2. 初回アクセス時に管理者アカウントの登録画面が表示される
3. メールアドレスとパスワードを入力して登録

### 6.2 ワークスペース作成

1. ログイン後、ワークスペース作成画面が表示される
2. ワークスペース名を入力（例: `My Team`）
3. URL スラッグを設定

### 6.3 カスタムワークフローステート設定

Plane CE では独自のワークフローステートを自由に定義できる。

1. **ワークスペース設定** → プロジェクトを選択 → **Settings** → **States**
2. デフォルトステート:
   - Backlog
   - Todo (Unstarted)
   - In Progress (Started)
   - Done (Completed)
   - Cancelled
3. 必要に応じてカスタムステートを追加:
   - 「+ Create new state」からステート名・カラー・グループを設定
   - グループは `Backlog` / `Unstarted` / `Started` / `Completed` / `Cancelled` から選択

参考: [Plane States ドキュメント](https://docs.plane.so/core-concepts/issues/states)

## Step 7: 動作確認

### 7.1 ワークアイテム (Issue) 作成テスト

1. プロジェクト内で **+** ボタンまたは `C` キーで Issue を作成
2. タイトル・説明・ステート・優先度を設定
3. ステート遷移（Todo → In Progress → Done）を確認

### 7.2 エクスポートテスト

1. **ワークスペース設定** → **Exports**
2. CSV / Excel / JSON のいずれかでエクスポート
3. ダウンロードしてデータを確認

### 7.3 API 疎通テスト

```bash
# API キーはワークスペース設定 → API Tokens で発行
API_KEY="your-api-key-here"

# ワークスペース一覧の取得
curl -s -H "x-api-key: ${API_KEY}" \
  https://plane.aloha-88.com/api/v1/workspaces/ | python3 -m json.tool

# プロジェクト一覧の取得
curl -s -H "x-api-key: ${API_KEY}" \
  https://plane.aloha-88.com/api/v1/workspaces/<workspace-slug>/projects/ | python3 -m json.tool
```

参考: [Plane REST API ドキュメント](https://developers.plane.so/)

---

## 運用

### ログ確認

```bash
docker compose logs -f api        # API ログ
docker compose logs -f worker     # ワーカーログ
docker compose logs -f proxy      # プロキシログ
```

### 停止・再起動

```bash
docker compose stop     # 停止
docker compose start    # 再開
docker compose restart  # 再起動
```

### バックアップ

```bash
# PostgreSQL のダンプ
docker compose exec plane-db pg_dump -U plane plane > backup_$(date +%Y%m%d).sql

# ボリュームごとバックアップする場合は Duplicati でボリュームマウントパスを対象に追加
```

### アップグレード

```bash
# .envのバージョンを更新、またはdocker-compose.ymlのイメージタグを変更
# 例: v1.2.3 → v1.3.0

docker compose pull    # 新しいイメージを取得
docker compose up -d   # 再起動（migratorが自動でDBマイグレーション実行）
```

---

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| コンテナが起動しない | `docker compose logs <service>` でログ確認 |
| migrator が失敗する | DB 接続を確認: `docker compose logs plane-db` |
| 502 Bad Gateway | API コンテナの起動待ち。1-2 分待って再試行 |
| Cloudflare で接続できない | Tunnel の URL が `http://<NAS-IP>:8082` か確認 |
| MinIO エラー | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` を確認 |

## 参考リンク

- [Plane 公式ドキュメント](https://docs.plane.so/)
- [Plane GitHub](https://github.com/makeplane/plane)
- [Plane REST API](https://developers.plane.so/)
- [Docker Compose セルフホスティング](https://developers.plane.so/self-hosting/methods/docker-compose)
- [ワークフローステート](https://docs.plane.so/core-concepts/issues/states)
