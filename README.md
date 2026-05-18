# salesforce-lesson-reschedule

Salesforce上の授業レコードを、Googleスプレッドシートの振替申請に基づいて自動更新するPythonスクリプトです。

---

## 背景・課題

塾の現場では、講師や生徒の都合により授業の振替が日常的に発生します。  
従来のフロー：

1. 講師がGoogleフォームで振替申請を送信
2. スプレッドシートに回答が蓄積される
3. **管理者が1件ずつSalesforceを手動で開き、開始・終了時間を修正する**

件数が増えると手作業の負担が大きく、ミスも発生しやすい状況でした。

---

## 解決策

このスクリプトはスプレッドシートの未処理行を自動検出し、Salesforce APIを通じて一括更新します。

```
[Googleフォーム回答] → [スプレッドシート] → [このスクリプト] → [Salesforce自動更新]
```

### 効率化の効果

| 項目 | 従来 | 自動化後 |
|------|------|----------|
| 1件あたりの作業時間 | 約3〜5分（Salesforce検索＋編集） | 0分（スクリプト実行のみ） |
| 月間件数（目安） | 20〜50件 | 同上 |
| ヒューマンエラー | 発生しうる（時間の入力ミス等） | 排除 |
| 処理漏れ | 発生しうる（手作業のため） | J列の状態管理で防止 |

---

## 使用技術

- **Python 3.10+**
- **[simple-salesforce](https://github.com/simple-salesforce/simple-salesforce)** — Salesforce REST API クライアント
- **[gspread](https://github.com/burnash/gspread)** — Google Sheets API クライアント
- **[google-auth](https://google-auth.readthedocs.io/)** — サービスアカウント認証
- **SOQL** — Salesforce Object Query Language（授業レコードの検索）
- **環境変数** — 認証情報をコードと分離して管理

---

## スプレッドシートの構成

| 列 | 内容 |
|----|------|
| A | タイムスタンプ（フォーム送信日時） |
| B | 講師氏名 |
| C | 生徒名 |
| D | 校舎・拠点 |
| E | 科目（複数可、区切り文字で分割） |
| F | 振替理由 |
| G | 変更前のテスト開始時間 |
| H | 変更後のテスト開始時間 |
| J | 処理ステータス（空欄=未処理、入力済み=スキップ） |

---

## 動作の仕組み

1. スプレッドシートの全行を読み込む
2. J列が空欄の行のみを処理対象とする
3. 科目数から授業時間（1科目=1時間）を計算し、新しい開始・終了時間を算出
4. SOQLで変更前の時間帯 ±2時間を検索し、対象レコードを特定
5. 講師名・生徒名はスペース（全角・半角）を除去してLIKE検索（表記ゆれ対策）
6. Salesforceのレコードを更新し、J列に処理日時を記録

### 時間計算ロジック

```
授業構成：[指導セッション (科目数×1時間)] → [テスト (科目数×1時間)]

テスト開始時間（スプシに記載）から逆算：
  新しい授業開始 = 変更後テスト開始 - 授業時間
  新しい授業終了 = 変更後テスト開始
```

---

## セットアップ

### 1. 依存パッケージのインストール

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install simple-salesforce gspread google-auth
```

### 2. Google サービスアカウントの準備

1. [Google Cloud Console](https://console.cloud.google.com/) でサービスアカウントを作成
2. Google Sheets API と Google Drive API を有効化
3. サービスアカウントキー（JSON）をダウンロードし、`service_account.json` として配置
4. スプレッドシートをサービスアカウントのメールアドレスと共有

### 3. 環境変数の設定

`.env.example` をコピーして `.env` を作成し、各値を設定します。

```bash
cp .env.example .env
```

```env
SF_USERNAME=your_username@example.com
SF_PASSWORD=your_password
SF_TOKEN=your_security_token
SF_DOMAIN=your-org.my
SPREADSHEET_ID=your_spreadsheet_id
SHEET_NAME=RescheduleRequests
```

### 4. 環境変数の読み込み

```bash
export $(cat .env | xargs)  # Linux/Mac
# Windows PowerShell:
Get-Content .env | ForEach-Object { $k,$v = $_ -split '=',2; [System.Environment]::SetEnvironmentVariable($k,$v) }
```

---

## 実行方法

```bash
# 変更内容を確認するだけ（Salesforceへの書き込みなし）
python lesson_reschedule.py --dry-run

# 実際に更新する
python lesson_reschedule.py
```

### 出力例

```
Connected to Salesforce.
Connected to Google Spreadsheet.

Row 3: Tanaka Taro / Yamada Hanako / Math English (2 subject(s))
  Original test start : 2026-05-20 14:00:00
  New test start      : 2026-05-21 14:00:00
  => New lesson window: 2026-05-21 12:00:00 - 2026-05-21 14:00:00
  Target: Yamada Hanako 指導枠 (a0B1234567890ABC)
  OK: Updated successfully.

===== Done =====
Success : 1
Skipped : 5
Errors  : 0
```

---

## ファイル構成

```
salesforce-lesson-reschedule/
├── lesson_reschedule.py   # メインスクリプト
├── .env.example           # 環境変数テンプレート
├── .gitignore
└── README.md
```

`service_account.json` と `.env` は `.gitignore` に含まれており、リポジトリには含まれません。

---

## 注意事項

- Salesforceの認証情報はコードに直接記述せず、必ず環境変数で管理してください
- `--dry-run` で動作を確認してから本番実行することを推奨します
- 複数レコードがヒットした場合は最初の1件を更新します（警告を出力）

---

## ライセンス

MIT
