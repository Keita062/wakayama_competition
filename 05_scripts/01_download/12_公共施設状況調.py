"""12_公共施設状況調 ダウンロードスクリプト

出典    : 総務省「公共施設状況調経年比較表」市町村経年比較表（平成18年度〜令和6年度）
発行    : 総務省 自治財政局
ページ  : https://www.soumu.go.jp/iken/shisetsu/index.html
ファイル: https://www.soumu.go.jp/main_content/001068878.xlsx
対象KPI : 人口あたり公園面積（都市公園等の面積・住民基本台帳人口、市区町村別。ガイドブックは2022年度＝令和4年度を使用）
取得日  : 2026-10-05（2026-10-06 に内容確認。再取得は不要）
加工は行わず、公表ファイルをそのまま保存する。

収録年度の確認（2026-10-06, pandas）:
  シート AFAHO14H1030 の A列「決算年度」は 2006〜2024 の各年度を収録（各年度 1,789行、和歌山県は30市町村＋県計）。
  都市公園等（都市計画区域内）の面積列（I列=市町村立 都市公園 面積, M列=市町村立 計 面積,
  O列=市町村立以外 面積, 単位㎡）は 2021〜2024 年度とも欠損なし。公園がない団体は「-」で表記。
  → 年度別（2021〜2024）の人口あたり公園面積はこの1ファイルで算出可能。
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
