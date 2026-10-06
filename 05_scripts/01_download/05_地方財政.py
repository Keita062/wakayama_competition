"""05_地方財政 ダウンロードスクリプト

出典    : 総務省（自治財政局財務調査課）
  (1) 地方公共団体の主要財政指標一覧（全市町村の主要財政指標）
      一覧ページ : https://www.soumu.go.jp/iken/shihyo_ichiran.html
      令和3年度  : https://www.soumu.go.jp/iken/zaisei/R03_chiho.html
          https://www.soumu.go.jp/main_content/000849999.xlsx
      令和5年度  : https://www.soumu.go.jp/menu_seisaku/toukei/02zaisei07_04000131.html
          https://www.soumu.go.jp/main_content/000983094.xlsx
  (2) 地方財政状況調査 令和3年度 市町村別決算状況調
      ページ : https://www.soumu.go.jp/iken/zaisei/r03_shichouson.html
          都市別 (1)概況          https://www.soumu.go.jp/main_content/000871018.xlsx
          都市別 (3)目的別歳出内訳 https://www.soumu.go.jp/main_content/000871020.xlsx
          町村別 (1)概況          https://www.soumu.go.jp/main_content/000871023.xlsx
          町村別 (3)目的別歳出内訳 https://www.soumu.go.jp/main_content/000871025.xlsx

対象KPI（年度はPDFの値と照合して決定）:
  - 実質公債費比率       … (1) 令和3年度（和歌山市9.6でPDFと一致）
  - 財政力指数（類型）   … (1) 令和5年度（和歌山市0.77・岩出市0.61でPDFと一致）
  - 歳出総額の教育費割合 … (2) 令和3年度 教育費 ÷ 歳出総額（和歌山市7.19・田辺市7.39でPDFと一致）

取得日  : 2026-10-05
加工は行わず、公表ファイルをそのまま保存する。
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "04_data" / "01_raw" / "05_地方財政"

FILES = {
    "R03_全市町村の主要財政指標_000849999.xlsx": "https://www.soumu.go.jp/main_content/000849999.xlsx",
    "R05_全市町村の主要財政指標_000983094.xlsx": "https://www.soumu.go.jp/main_content/000983094.xlsx",
    "R03_市町村別決算状況調_都市別_01概況_000871018.xlsx": "https://www.soumu.go.jp/main_content/000871018.xlsx",
    "R03_市町村別決算状況調_都市別_03目的別歳出内訳_000871020.xlsx": "https://www.soumu.go.jp/main_content/000871020.xlsx",
    "R03_市町村別決算状況調_町村別_01概況_000871023.xlsx": "https://www.soumu.go.jp/main_content/000871023.xlsx",
    "R03_市町村別決算状況調_町村別_03目的別歳出内訳_000871025.xlsx": "https://www.soumu.go.jp/main_content/000871025.xlsx",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        (OUT / name).write_bytes(r.content)
        print(f"saved {name} ({len(r.content):,} bytes)")


if __name__ == "__main__":
    main()
