"""03_社会人口統計体系 ダウンロードスクリプト

出典    : 社会・人口統計体系「統計でみる市区町村のすがた2026」（総務省統計局）
公開元  : 政府統計の総合窓口 e-Stat
公式ページ:
  - 統計局 https://www.stat.go.jp/data/s-sugata/naiyou.html
  - e-Stat https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&lid=000001484933
           （提供統計名「統計でみる市区町村のすがた2026」基礎データ, 公開日 2026-06-19）

取得ファイル（全国全市区町村を収録した分野別Excel。加工なしの原本）:
  2026-b.xls  B 自然環境  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040463585&fileKind=0
              → 総面積(B1101), 可住地面積(B1103)  [2024年]（人口密度, 可住地面積割合）
  2026-d.xls  D 行政基盤  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040463587&fileKind=0
              → 財政力指数(D2201)  [2022年度]（任意項目）
  2026-e.xls  E 教育      https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040463588&fileKind=0
              → 幼稚園数(E1101), 高等学校数(E4101)  [2024年, 学校基本調査]

補足（飲食店数）:
  「統計でみる市区町村のすがた」および社会・人口統計体系の市区町村データには「飲食店」単独の
  事業所数がない（あるのは大分類「宿泊業，飲食サービス業」のみ）。そのため、その元データである
  令和3年経済センサス‐活動調査（総務省・経済産業省）の市区町村別 産業中分類表を併せて取得する。
  b1_006_1.xlsx  事業所に関する集計 第6-1表 産業(中分類)別民営事業所数… －全国、都道府県、市区町村
              https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040067880&fileKind=0
              公式ページ https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200553&tstat=000001145590
              → 産業中分類「76_飲食店」の事業所数  [2021年6月1日]（可住地面積あたり飲食店数）

取得日  : 2026-10-05
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT_DIR = BASE / "04_data" / "01_raw" / "03_社会人口統計体系"

URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind=0"
FILES = {
    "2026-b.xls": "000040463585",     # すがた2026 B 自然環境
    "2026-d.xls": "000040463587",     # すがた2026 D 行政基盤
    "2026-e.xls": "000040463588",     # すがた2026 E 教育
    "b1_006_1.xlsx": "000040067880",  # 経済センサス‐活動調査2021 第6-1表（飲食店数）
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, stat_inf_id in FILES.items():
        url = URL.format(stat_inf_id)
        r = requests.get(url, timeout=600)
        r.raise_for_status()
        path = OUT_DIR / name
        path.write_bytes(r.content)
        print(f"saved {path.name} ({len(r.content):,} bytes) <- {url}")


if __name__ == "__main__":
    main()
