"""03_社会人口統計体系 ダウンロードスクリプト

出典    : 社会・人口統計体系「統計でみる市区町村のすがた」2024・2025・2026（総務省統計局）
公開元  : 政府統計の総合窓口 e-Stat
公式ページ:
  - 統計局 https://www.stat.go.jp/data/s-sugata/naiyou.html
  - e-Stat すがた2026 https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&lid=000001484933
           （提供統計名「統計でみる市区町村のすがた2026」基礎データ, 公開日 2026-06-19, tstat=000001244297）
  - e-Stat すがた2025 https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200502&tstat=000001229545
  - e-Stat すがた2024 https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200502&tstat=000001218560

取得ファイル（全国全市区町村を収録した分野別Excel。加工なしの原本）:
  ※ 各版の収録データ年はファイル10行目（0始まりで9行目）の年次欄で確認済み。
     版ごとの列配置は同一（B: K列=総面積 B1101, L列=可住地面積 B1103 /
     E: K列=幼稚園数 E1101, S列=高等学校数 E4101 / 市区町村コードは最終列）。
  2026-b.xls  B 自然環境  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040463585&fileKind=0
              → 総面積(B1101), 可住地面積(B1103)  [2024年]
  2025-b.xls  B 自然環境  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040283811&fileKind=0
              → 同上  [2023年]
  2024-b.xls  B 自然環境  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040186222&fileKind=0
              → 同上  [2022年]
  2026-d.xls  D 行政基盤  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040463587&fileKind=0
              → 財政力指数(D2201)  [2022年度]（任意項目）
  2026-e.xls  E 教育      https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040463588&fileKind=0
              → 幼稚園数(E1101), 高等学校数(E4101)  [2024年, 学校基本調査 5月1日現在]
  2025-e.xls  E 教育      https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040283814&fileKind=0
              → 同上  [2023年]
  2024-e.xls  E 教育      https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040186225&fileKind=0
              → 同上  [2022年]
  ※ 2024年版は浜松市の区再編（2024-01-01）前のため7区で収録（行数が4行多い）。
     2025年版・2026年版の浜松市中央区・浜名区は一部項目が「...」。

補足（2025年の幼稚園数・高等学校数）:
  「統計でみる市区町村のすがた2027」（2025年データ）は取得日時点で未公表のため、元データである
  文部科学省「学校基本調査」令和7年度（2025-05-01現在, 確定値 公開日 2025-12-26）の市町村別集計を取得する。
  公式ページ https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00400001&tstat=000001011528
  ey0323_1_2025.xlsx  幼稚園 表番号eyx-1 市町村別学校数
              https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040393408&fileKind=0
  ey0328_1_2025.xlsx  高等学校 表番号eyx-124 市町村別学校数 計
              https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040393531&fileKind=0
  レイアウト: 都道府県ごとに1シート（先頭は「全国」）。A列=都道府県内3桁の市町村コード、B列=市町村名、
  C列（「計/計/計」）が学校数の総数。7行目（0始まり5行目）が都道府県計、以降が市町村（政令市は区単位、
  政令市計の行はない。東京都外・大阪市外の行あり）。5桁コードは「シート順の都道府県番号2桁＋A列3桁」。
  令和6年度版の同表C列は、すがた2026（2024年）のE1101・E4101と全市区町村で完全一致することを確認済み。

補足（飲食店数）:
  「統計でみる市区町村のすがた」および社会・人口統計体系の市区町村データには「飲食店」単独の
  事業所数がない（あるのは大分類「宿泊業，飲食サービス業」のみ）。そのため、その元データである
  令和3年経済センサス‐活動調査（総務省・経済産業省）の市区町村別 産業中分類表を併せて取得する。
  b1_006_1.xlsx  事業所に関する集計 第6-1表 産業(中分類)別民営事業所数… －全国、都道府県、市区町村
              https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040067880&fileKind=0
              公式ページ https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200553&tstat=000001145590
              → 産業中分類「76_飲食店」の事業所数  [2021年6月1日]（可住地面積あたり飲食店数）

取得日  : 2026-10-05（2026-b/d/e, b1_006_1）, 2026-10-06（2024-b/e, 2025-b/e, ey0323_1_2025, ey0328_1_2025）
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT_DIR = BASE / "04_data" / "01_raw" / "03_社会人口統計体系"

URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind=0"
FILES = {
    "2026-b.xls": "000040463585",     # すがた2026 B 自然環境（2024年）
    "2026-d.xls": "000040463587",     # すがた2026 D 行政基盤
    "2026-e.xls": "000040463588",     # すがた2026 E 教育（2024年）
    "2025-b.xls": "000040283811",     # すがた2025 B 自然環境（2023年）
    "2025-e.xls": "000040283814",     # すがた2025 E 教育（2023年）
    "2024-b.xls": "000040186222",     # すがた2024 B 自然環境（2022年）
    "2024-e.xls": "000040186225",     # すがた2024 E 教育（2022年）
    "ey0323_1_2025.xlsx": "000040393408",  # 学校基本調査R7 幼稚園 市町村別学校数（2025年）
    "ey0328_1_2025.xlsx": "000040393531",  # 学校基本調査R7 高等学校 市町村別学校数 計（2025年）
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
