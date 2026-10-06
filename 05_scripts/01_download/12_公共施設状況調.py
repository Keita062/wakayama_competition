"""12_公共施設状況調 ダウンロードスクリプト

出典    : 総務省「公共施設状況調経年比較表」市町村経年比較表（平成18年度〜令和6年度）
発行    : 総務省 自治財政局
ページ  : https://www.soumu.go.jp/iken/shisetsu/index.html
ファイル: https://www.soumu.go.jp/main_content/001068878.xlsx
対象KPI : 人口あたり公園面積（都市公園等の面積・住民基本台帳人口、市区町村別。ガイドブックは2022年度＝令和4年度を使用）
取得日  : 2026-10-05
加工は行わず、公表ファイルをそのまま保存する。
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "04_data" / "01_raw" / "12_公共施設状況調"

FILES = {
    "市町村経年比較表_H18-R06_001068878.xlsx": "https://www.soumu.go.jp/main_content/001068878.xlsx",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        (OUT / name).write_bytes(r.content)
        print(f"saved {name} ({len(r.content):,} bytes)")


if __name__ == "__main__":
    main()
