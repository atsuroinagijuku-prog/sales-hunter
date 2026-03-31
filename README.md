# Sales Hunter - AI営業代行エージェントシステム

Gemini AIを活用したBtoB営業メール自動化システムです。見込み顧客のスコアリング、初回メール生成・送信、返信分類、フォローアップ生成までを自動化します。

---

## システム概要

```
データフロー:
CSV入力 → エンリッチメント → スコアリング → メール生成 → 送信
                                                              ↓
                                              返信フェッチ ← Gmail
                                                              ↓
                                              返信分類 → フォローアップ生成
                                                              ↓
                                                         レポート出力
```

### 主要コンポーネント

| コンポーネント | 役割 |
|--------------|------|
| `ProspectEnricher` | メール検証・ドメインブロック・重複排除 |
| `LeadScoringAgent` | ルールベーススコアリング（0〜100点） |
| `OutreachMessageAgent` | Gemini AIによる初回営業メール生成 |
| `OutreachSender` | Gmail API経由でメール送信 |
| `ReplyFetcher` | GmailからINBOXの返信を取得・マッチング |
| `ReplyClassifier` | ルールベース＋AIによる返信分類 |
| `FollowupMessageAgent` | 返信ラベルに応じたフォローアップ生成 |
| `ReportAgent` | JSON/Markdownレポート出力 |
| `CRMStateManager` | ファイルベースの状態管理（JSON） |

---

## セットアップ方法

### 1. リポジトリのクローン

```bash
git clone <repo_url>
cd sales-hunter
```

### 2. 仮想環境の作成と依存関係のインストール

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 環境変数の設定

`.env.example` をコピーして `.env` を作成し、各値を設定します。

```bash
cp .env.example .env
```

`.env` ファイルの内容:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_API_KEY=your_gemini_api_key_here
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REFRESH_TOKEN=your_google_refresh_token
GMAIL_FROM_ADDRESS=your@gmail.com
```

#### Gemini API キーの取得

1. [Google AI Studio](https://aistudio.google.com/app/apikey) にアクセス
2. APIキーを生成し、`GEMINI_API_KEY` に設定

### 4. Gmail API の設定

#### OAuth2認証情報の取得

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. 「APIとサービス」→「ライブラリ」から **Gmail API** を有効化
3. 「認証情報」→「OAuth 2.0 クライアントID」を作成（種類: デスクトップアプリ）
4. クライアントID・クライアントシークレットを `.env` に設定

#### リフレッシュトークンの取得

```bash
pip install google-auth-oauthlib
python - <<'EOF'
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": "YOUR_CLIENT_ID",
            "client_secret": "YOUR_CLIENT_SECRET",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=["https://www.googleapis.com/auth/gmail.modify"],
)
creds = flow.run_local_server(port=0)
print("Refresh token:", creds.refresh_token)
EOF
```

取得したリフレッシュトークンを `GOOGLE_REFRESH_TOKEN` に設定します。

---

## 実行コマンド一覧

### 見込み顧客のインポート

```bash
python main.py ingest
python main.py ingest --input data/input/my_prospects.csv
python main.py ingest --dry-run  # 実行内容の確認のみ
```

### スコアリング

```bash
python main.py score
python main.py score --dry-run
```

### 初回メール送信

```bash
python main.py send-first                # 全件送信（daily_send_limit適用）
python main.py send-first --limit 5      # 最大5件送信
python main.py send-first --dry-run      # 送信シミュレーション
python main.py send-first --draft        # メール生成のみ（送信しない）
```

### 返信の取得

```bash
python main.py fetch-replies
python main.py fetch-replies --dry-run
```

### 返信の処理（分類＋フォローアップ生成）

```bash
python main.py process-replies
python main.py process-replies --dry-run
```

### レポート生成

```bash
python main.py generate-report
```

### 典型的なワークフロー

```bash
# 1. 見込み顧客をインポート
python main.py ingest

# 2. スコアリング
python main.py score

# 3. メッセージ生成のみ確認（ドラフトモード）
python main.py send-first --draft

# 4. 実際に送信（dry-runで最終確認）
python main.py send-first --dry-run
python main.py send-first --limit 10

# 5. 返信を取得・処理
python main.py fetch-replies
python main.py process-replies

# 6. レポート確認
python main.py generate-report
```

---

## dry-run / draft モードの使い方

| オプション | 動作 |
|-----------|------|
| `--dry-run` | メール送信をスキップ。ログに「DRY-RUN」と表示。CRM状態は更新される（FIRST_SENT扱い） |
| `--draft` | `send-first` 専用。メッセージを生成してCRMに保存するが、送信しない。ステータスはSCOREDのまま |

---

## Prospect CSV の列定義

| 列名 | 必須 | 説明 |
|------|------|------|
| `company_name` | 必須 | 会社名 |
| `contact_email` | 必須 | 担当者メールアドレス |
| `website` | 任意 | 企業ウェブサイトURL |
| `contact_name` | 任意 | 担当者名 |
| `industry` | 任意 | 業種（スコアリングに影響） |
| `notes` | 任意 | 備考・ニーズ情報（スコアリングに大きく影響） |

---

## スコアリングルールの変更方法

`config.yaml` の `score_rules` セクションを編集します。

```yaml
score_rules:
  has_email: 20          # メールアドレスがある場合の加点
  has_website: 10        # WebサイトURLがある場合の加点
  allowed_industry: 15   # 対象業種に含まれる場合の加点
  btob_signal: 5         # 株式会社/合同会社/有限会社を含む場合の加点
  notes_max_bonus: 40    # notesキーワード加点の上限
  notes_keywords:        # notesに含まれると加点されるキーワード
    外注: 20
    代行: 20
    自動化: 20
    効率化: 20
    マーケ: 15
    営業: 15
    リスト: 15
    入力: 10
```

優先度の閾値:
- **high**: スコア 70以上
- **medium**: スコア 40〜69
- **low**: スコア 39以下

対象業種の変更は `targeting.allowed_industries` で行います。

---

## ディレクトリ構成

```
sales-hunter/
├── main.py                    # CLIエントリーポイント
├── requirements.txt
├── config.yaml                # 設定ファイル
├── .env.example               # 環境変数テンプレート
├── app/
│   ├── core/engine.py         # メインオーケストレーター
│   ├── agents/                # AIエージェント
│   │   ├── lead_scoring.py
│   │   ├── outreach_message.py
│   │   ├── reply_classifier.py
│   │   ├── followup_message.py
│   │   └── report_agent.py
│   ├── services/              # ビジネスサービス
│   │   ├── prospect_source.py
│   │   ├── prospect_enricher.py
│   │   ├── outreach_sender.py
│   │   ├── reply_fetcher.py
│   │   └── crm_state.py
│   ├── models/prospect.py     # Pydanticデータモデル
│   ├── integrations/          # 外部API統合
│   │   ├── llm_client.py      # Gemini AIクライアント
│   │   └── gmail_client.py    # Gmail APIクライアント
│   └── utils/logger.py        # ロギング設定
├── prompts/                   # LLMプロンプトテンプレート
├── data/
│   ├── input/                 # CSVインプット
│   ├── output/                # レポート・送信ログ
│   ├── logs/                  # アプリケーションログ
│   └── state/                 # CRM状態ファイル（prospects.json）
```

---

## 出力ファイル

| ファイル | 説明 |
|---------|------|
| `data/state/prospects.json` | 全見込み顧客の状態（CRM） |
| `data/output/send_log.jsonl` | 送信履歴（JSONL形式） |
| `data/output/report_YYYYMMDD.json` | レポート（JSON） |
| `data/output/report_YYYYMMDD.md` | レポート（Markdown） |
| `data/logs/sales_hunter.log` | アプリケーションログ |

---

## 今後の拡張案

1. **Webスクレイピング統合**: 企業WebサイトからAIで業種・ニーズを自動抽出
2. **LinkedIn連携**: LinkedIn Sales NavigatorからリードをCSV出力して取り込み
3. **Slack通知**: 返信があった際にSlackチャンネルへ通知
4. **スケジューラー**: cronまたはCloud Schedulerで毎日自動実行
5. **ダッシュボード**: Streamlitを使ったリアルタイム可視化UI
6. **マルチプロバイダーLLM**: OpenAI / Claude対応（プロバイダー切り替え）
7. **A/Bテスト**: 複数の件名・本文テンプレートのテスト機能
8. **CRM統合**: HubSpot / Salesforce / Notion DBとの同期
9. **バウンス処理**: 配信失敗メールの自動検出・除外
10. **送信レート制御**: 時間帯別の送信最適化（開封率向上）
