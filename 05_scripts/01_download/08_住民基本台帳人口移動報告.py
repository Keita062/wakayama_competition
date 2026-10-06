"""08_住民基本台帳人口移動報告 ダウンロード

- 統計名  : 住民基本台帳人口移動報告 2024年（令和6年）結果 年報（実数）
- 作成機関: 総務省統計局
- 公式ページ: https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200523&tstat=000000070001&cycle=7&year=20240&tclass1val=0
- ファイルURL（Excel, 2025-04-24公開）:
    表番号11-1 年齢(5歳階級)、男女別他市区町村からの転入者数－全国、都道府県、市区町村
        https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040271506&fileKind=0  (b01101s.xlsx)
    表番号11-2 年齢(5歳階級)、男女別他市区町村への転出者数－全国、都道府県、市区町村
        https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040271507&fileKind=0  (b01102s.xlsx)
    表番号11-3 年齢(5歳階級)、男女別転入超過数－全国、都道府県、市区町村
        https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040271508&fileKind=0  (b01103s.xlsx)
- 対象KPI : 転入超過割合（転入超過数 / 人口）
- 取得日  : 2026-10-05
"""
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parents[2] / "04_data" / "01_raw" / "08_住民基本台帳人口移動報告"
FILES = {
    "b01101s_表11-1_他市区町村からの転入者数_2024.xlsx": "000040271506",
    "b01102s_表11-2_他市区町村への転出者数_2024.xlsx": "000040271507",
    "b01103s_表11-3_転入超過数_2024.xlsx": "000040271508",
}
URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind=0"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, sid in FILES.items():
        r = requests.get(URL.format(sid), timeout=180)
        r.raise_for_status()
        (OUT_DIR / name).write_bytes(r.content)
        print(f"saved {name} ({len(r.content):,} bytes)")


if __name__ == "__main__":
    main()
