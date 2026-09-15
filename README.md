# salesforce-lesson-reschedule

> Googleフォームの振替申請をSalesforceへ自動反映し、月20〜50件の手作業をゼロにした業務自動化スクリプト

講師・生徒の都合による授業振替が日常的に発生する塾の現場で、管理者のボトルネックを解消。スプレッドシートの未処理行を自動検出し、Salesforce APIで授業時間を一括更新します。

## 解決した課題

| 項目 | Before | After |
|---|---|---|
| 1件あたりの作業時間 | 約3〜5分（Salesforce検索＋編集） | 0分（スクリプト実行のみ） |
| 月間件数（目安） | 20〜50件 | 同上 |
| ヒューマンエラー | 発生しうる（時間の入力ミス等） | 排除 |
| 処理漏れ | 発生しうる | J列のステータス管理で防止 |

## 背景・導入経緯

講師・生徒の都合による授業振替は日常的に発生する。振替申請は Google フォームで受け付けていたが、Salesforce のレコード更新は管理者が手動で行っていた。1件あたり3〜5分、月間20〜50件の手作業が担当者のボトルネックになっていた。

フォーム回答がスプレッドシートに蓄積されるフローはすでにあったため、そこから Salesforce への自動反映のみをスクリプトで担うシンプルな設計にした。既存の申請フローを変えずにSalesforce 更新だけを自動化している。

## 技術スタック

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Salesforce](https://img.shields.io/badge/Salesforce-00A1E0?style=flat&logo=salesforce&logoColor=white)
![Google Sheets](https://img.shields.io/badge/Google%20Sheets-34A853?style=flat&logo=google-sheets&logoColor=white)

- **Python 3.10+**
- **simple-salesforce** — Salesforce REST API クライアント
- **gspread** — Google Sheets API クライアント
- **google-auth** — サービスアカウント認証
- **SOQL** — 授業レコードの検索・特定

## 処理フロー

```
[Googleフォーム回答]
  ↓
[スプレッドシート（J列が空欄の行のみ処理対象）]
  ↓
lesson_reschedule.py
（時間計算 → SOQL検索 → LIKE検索で表記ゆれ吸収 → Salesforce更新）
  ↓
[Salesforce 授業レコード自動更新 + J列に処理日時を記録]
```

## 実装上の工夫

- 講師名・生徒名のスペース（全角・半角）を除去した **LIKE 検索**で表記ゆれに対応
- 変更前の開始時刻の **-2時間〜+1時間**に検索窓を絞る。氏名だけでは同じ生徒の別日程に当たるため
- ステータスが `Cancelled` / `Completed` のレコードは検索対象から外す
- 「テスト開始時間」から逆算して授業開始・終了を算出（科目数×1時間のロジック）
- J列のステータス管理で**冪等性**を担保（複数回実行しても二重更新しない）
- `--dry-run` フラグでSalesforceへの書き込みなしに動作確認が可能

## セットアップ

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install simple-salesforce gspread google-auth
```

### 環境変数

**スクリプトは `.env` を自分では読み込みません**（`os.environ` を直接参照します）。
シェルに読み込ませてから実行してください。

```bash
cp .env.example .env
set -a && . ./.env && set +a
```

| 環境変数 | 説明 | 未設定時 |
|---|---|---|
| `SF_USERNAME` | Salesforce ユーザー名 | 認証に失敗する |
| `SF_PASSWORD` | Salesforce パスワード | 認証に失敗する |
| `SF_TOKEN` | Salesforce セキュリティトークン | 認証に失敗する |
| `SF_DOMAIN` | ログイン先のドメイン | `your-org.my` |
| `SPREADSHEET_ID` | 対象スプレッドシートのID | `YOUR_SPREADSHEET_ID` |
| `SHEET_NAME` | 対象シート名 | `RescheduleRequests` |

### サービスアカウント

Google Sheets API を有効にしたサービスアカウントのJSONキーを、
**`service_account.json` という名前でカレントディレクトリに置いてください**（パスは固定です）。
そのうえで、サービスアカウントのメールアドレスを対象スプレッドシートに「編集者」として共有します。
共有していないとスプレッドシートを開けずに終了します。

## 使い方

```bash
# 動作確認（Salesforceへの書き込みなし）
python lesson_reschedule.py --dry-run

# 本番実行
python lesson_reschedule.py
```

出力例:

```
Connected to Salesforce.
Connected to Google Spreadsheet.

Row 3: <講師名> / <生徒名> / 数学 英語 (2 subject(s))
  Original test start : 2026-05-20 14:00:00
  New test start      : 2026-05-21 14:00:00
  => New lesson window: 2026-05-21 12:00:00 - 2026-05-21 14:00:00
  Target: <授業名> (a0X0000000XXXXX)
  OK: Updated successfully.

===== Done =====
Success : 1
Skipped : 5
Errors  : 0
```

`--dry-run` では最後の2行が `[DRY RUN] Would update to: ...` に変わり、
Salesforceにもスプレッドシートにも書き込みません。

このリポジトリにテストは置いていません。動作確認は `--dry-run` で行います。

## スプレッドシートの列構成

Googleフォームの回答がそのまま蓄積される前提です。J列だけをスクリプトが書き込みます。

| 列 | 内容 |
|---|---|
| A | タイムスタンプ（フォーム自動入力） |
| B | 講師名 |
| C | 生徒名 |
| D | 校舎・拠点 |
| E | 科目（`・` `、` `,` 空白のいずれかで区切る。区切り数から授業時間を算出） |
| F | 申請理由（スクリプトは読まない） |
| G | 変更前のテスト開始時間 |
| H | 変更後のテスト開始時間 |
| J | 処理ステータス（**空欄の行だけが処理対象**。成功で `auto-updated <日時>`、失敗で `Error: ...` が入る） |

**J列を「処理済みの印」ではなく「処理した日時」にしてある**ので、いつ反映されたかを後から追えます。フォーム側の書式を変えずに済むよう、既存の申請フローには手を入れていません。

## 運用上の前提

- **表記ゆれは LIKE 検索で吸収する。** 講師名・生徒名の姓名間の空白（全角・半角）は入力者によって揺れるため、空白を除去した部分一致でレコードを特定します
- **複数のレコードが一致したときは、警告を出して先頭（開始時刻が最も早いもの）を更新します。** `WARNING: N records matched. Using the first one.` が出ますが、処理は止まりません。同姓同名や、同じ時間帯に複数の枠がある運用では誤ったレコードを書き換えうるので、その規模で使う場合は氏名ではなくIDで突き合わせる必要があります
- **失敗した行のJ列にはエラー文が入り、その行は次回以降スキップされます。** 処理対象はJ列が空欄の行だけなので、原因を直したあとはJ列を手で空にしてから再実行してください
- **`--dry-run` を先に通す。** Salesforceへの書き込みは取り消せないので、対象行と算出した時刻を確認してから本番実行します

## ファイル構成

```
salesforce-lesson-reschedule/
├── lesson_reschedule.py   # メインスクリプト
├── .env.example           # 環境変数テンプレート
├── .gitignore
├── LICENSE
└── README.md
```

## ライセンス

MIT
