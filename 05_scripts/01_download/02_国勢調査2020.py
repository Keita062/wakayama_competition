"""02_国勢調査2020 ダウンロードスクリプト

出典    : 令和2年国勢調査（総務省統計局）
公開元  : 政府統計の総合窓口 e-Stat
公式ページ:
  - 人口等基本集計   https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200521&tstat=000001136464&cycle=0&tclass1=000001136466&layout=datalist&tclass2val=0
  - 就業状態等基本集計 https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200521&tstat=000001136464&cycle=0&tclass1=000001136467&layout=datalist&tclass2val=0

取得ファイル（いずれも 全国・都道府県・市区町村 の全国一括Excel。加工なしの原本）:
  b02_07.xlsx  人口等基本集計 第2-7表  男女，年齢（5歳階級及び3区分）別人口
               https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032142410&fileKind=0
               → 総人口, 65歳以上人口（高齢化率）
  b04_03.xlsx  人口等基本集計 第4-3表  男女，年齢，配偶関係別人口（15歳以上）
               https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032142476&fileKind=0
               → 未婚/有配偶/死別/離別（既婚者割合）
  b27_04.xlsx  人口等基本集計 第27-4表 世帯の家族類型，65歳以上世帯員の有無別一般世帯数
               https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032142643&fileKind=0
               → 一般世帯総数, 核家族世帯, 核家族以外の世帯（拡大家族世帯割合）,
                 65歳以上の単独世帯（高齢単身世帯割合）
  c01_02.xlsx  就業状態等基本集計 第1-2表 男女，年齢，労働力状態別人口（15歳以上）
               https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032201175&fileKind=0
               → 労働力人口, 完全失業者（完全失業率, 完全失業者数の人口比）
  c05_03.xlsx  就業状態等基本集計 第5-3表 男女，従業上の地位，産業（大分類）別就業者数
               https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032201183&fileKind=0
               → 産業3部門別就業者数（第1次産業就業者割合）

調査時点: 2020年10月1日
取得日  : 2026-10-05
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT_DIR = BASE / "04_data" / "01_raw" / "02_国勢調査2020"

URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind=0"
FILES = {
    "b02_07.xlsx": "000032142410",
    "b04_03.xlsx": "000032142476",
    "b27_04.xlsx": "000032142643",
    "c01_02.xlsx": "000032201175",
    "c05_03.xlsx": "000032201183",
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
