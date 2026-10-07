"""08_住民基本台帳人口移動報告 ダウンロード

- 統計名  : 住民基本台帳人口移動報告 年報（実数） 2022年〜2025年 結果
- 作成機関: 総務省統計局
- 公式ページ（年報（実数）2020年～、年別）:
    https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00200523&tstat=000000070001&cycle=7&year={YYYY}0&tclass1=000001148746&tclass1val=0&tclass2val=0
    （{YYYY} = 2022 / 2023 / 2024 / 2025）
- 対象表（各年 Excel）:
    表番号11-1 年齢(5歳階級)、男女別他市区町村からの転入者数－全国、都道府県、市区町村 (b01101s.xlsx)
    表番号11-2 年齢(5歳階級)、男女別他市区町村への転出者数－全国、都道府県、市区町村 (b01102s.xlsx)
    表番号11-3 年齢(5歳階級)、男女別転入超過数－全国、都道府県、市区町村           (b01103s.xlsx)
- ファイルURL: https://www.e-stat.go.jp/stat-search/file-download?statInfId={statInfId}&fileKind=0
    年    11-1          11-2          11-3          e-Stat公開（更新）日
    2022  000040008304  000040008305  000040008306  2023-01-30
    2023  000040139324  000040139325  000040139326  2024-01-30
    2024  000040271506  000040271507  000040271508  2025-04-24
    2025  000040428748  000040428749  000040428750  2026-04-23
- 対象KPI : 転入超過割合（転入超過数 / 人口）
- 取得日  : 2026-10-05（2024年）、2026-10-06（2022・2023・2025年）
"""
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parents[2] / "04_data" / "01_raw" / "08_住民基本台帳人口移動報告"

# 年 -> (表11-1, 表11-2, 表11-3) の statInfId
STAT_INF_IDS = {
    2022: ("000040008304", "000040008305", "000040008306"),
    2023: ("000040139324", "000040139325", "000040139326"),
    2024: ("000040271506", "000040271507", "000040271508"),
    2025: ("000040428748", "000040428749", "000040428750"),
}
NAME_TEMPLATES = (
    "b01101s_表11-1_他市区町村からの転入者数_{year}.xlsx",
    "b01102s_表11-2_他市区町村への転出者数_{year}.xlsx",
    "b01103s_表11-3_転入超過数_{year}.xlsx",
)
URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind=0"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for year, sids in STAT_INF_IDS.items():
        for tmpl, sid in zip(NAME_TEMPLATES, sids):
            name = tmpl.format(year=year)
            r = requests.get(URL.format(sid), timeout=180)
            r.raise_for_status()
            (OUT_DIR / name).write_bytes(r.content)
            print(f"saved {name} ({len(r.content):,} bytes) <- statInfId={sid}")


if __name__ == "__main__":
    main()
