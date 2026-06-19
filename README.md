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
- 「テスト開始時間」から逆算して授業開始・終了を算出（科目数×1時間のロジック）
- J列のステータス管理で**冪等性**を担保（複数回実行しても二重更新しない）
- `--dry-run` フラグでSalesforceへの書き込みなしに動作確認が可能

## セットアップ

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install simple-salesforce gspread google-auth
cp .env.example .env
# .env に実値を入れる
```

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

Row 3: <講師名> / <生徒名> / Math English (2 subject(s))
  Original test start : 2026-05-20 14:00:00
  New test start      : 2026-05-21 14:00:00
  => New lesson window: 2026-05-21 12:00:00 - 2026-05-21 14:00:00
  OK: Updated successfully.

===== Done =====
Success : 1 / Skipped : 5 / Errors : 0
```

## ファイル構成

```
salesforce-lesson-reschedule/
├── lesson_reschedule.py   # メインスクリプト
├── .env.example           # 環境変数テンプレート
├── .gitignore
└── README.md
```

## ライセンス

MIT
