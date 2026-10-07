"""15_年齢別人口 ダウンロードスクリプト

目的    : 市区町村ごとの「性別×年代（10歳階級）」人口を作るため、男女・年齢（5歳階級）別人口を
          全国の市区町村について1ファイルで収録した表を取得する。

出典    : 令和2年国勢調査 人口等基本集計（総務省統計局）
公開元  : 政府統計の総合窓口 e-Stat
公式ページ:
  - 令和2年国勢調査 https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200521&tstat=000001136464
  - 人口等基本集計   https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200521&tstat=000001136464&cycle=0&tclass1=000001136466&layout=datalist&tclass2val=0

取得ファイル（全国・都道府県・市区町村の全国一括Excel。加工なしの原本）:
  b02_07.xlsx  人口等基本集計 第2-7表 男女，年齢（5歳階級及び3区分），国籍総数か日本人別人口，平均年齢，
               年齢中位数及び人口構成比［年齢別］－全国，都道府県，市区町村（2000年（平成12年）市区町村含む）
               statInfId=000032142410
               https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032142410&fileKind=0
               → 男女別・5歳階級別人口（0〜4歳 … 100歳以上、年齢「不詳」）
  ※ 02_国勢調査2020/b02_07.xlsx（総人口・高齢化率に使用）と同じ表。本スクリプトでは年齢別人口用の
     原本として 15_年齢別人口/ に保存し直す（バイト単位で同一であることを確認済み）。

調査時点: 2020年10月1日
取得日  : 2026-10-07
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT_DIR = BASE / "04_data" / "01_raw" / "15_年齢別人口"

HEADERS = {"User-Agent": "Mozilla/5.0"}
URL = "https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind=0"
FILES = {
    "b02_07.xlsx": "000032142410",   # 国勢調査2020 人口等基本 第2-7表（男女，年齢5歳階級別人口）
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, stat_inf_id in FILES.items():
        url = URL.format(stat_inf_id)
        r = requests.get(url, timeout=600, headers=HEADERS)
        r.raise_for_status()
        path = OUT_DIR / name
        path.write_bytes(r.content)
        print(f"saved {path.name} ({len(r.content):,} bytes) <- {url}")


if __name__ == "__main__":
    main()
