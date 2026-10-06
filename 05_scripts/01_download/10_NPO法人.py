"""10_NPO法人 ダウンロード

- データ名: NPO法人情報の一括ダウンロード（全所轄庁）行政入力情報データ
- 作成機関: 内閣府 NPO法人ポータルサイト
- 公式ページ: https://www.npo-homepage.go.jp/npoportal/download/all
- ファイルURL: https://www.npo-homepage.go.jp/npoportal/download/zip/gyousei_000.zip
    （ZIP内にCSV。所轄庁が入力した法人名・主たる事務所の所在地・認証日・解散日等を全法人分収録。
      ポータルのデータは毎日更新され、取得時点のスナップショットとなる）
- 対象KPI : 人口あたりNPOの数（主たる事務所の所在地が当該市区町村の法人数）
- 取得日  : 2026-10-05（ページ記載のデータ時点: 2026年10月04日）
"""
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parents[2] / "04_data" / "01_raw" / "10_NPO法人"
URL = "https://www.npo-homepage.go.jp/npoportal/download/zip/gyousei_000.zip"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=300)
    r.raise_for_status()
    out = OUT_DIR / "gyousei_000.zip"
    out.write_bytes(r.content)
    print(f"saved {out.name} ({len(r.content):,} bytes)")


if __name__ == "__main__":
    main()
