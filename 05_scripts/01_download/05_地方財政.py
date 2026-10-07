"""05_地方財政 ダウンロードスクリプト

出典    : 総務省（自治財政局財務調査課）
  (1) 地方公共団体の主要財政指標一覧（全市町村の主要財政指標）  令和3〜6年度
      一覧ページ : https://www.soumu.go.jp/iken/shihyo_ichiran.html
      令和3年度  : https://www.soumu.go.jp/iken/zaisei/R03_chiho.html
          https://www.soumu.go.jp/main_content/000849999.xlsx
      令和4年度  : https://www.soumu.go.jp/iken/zaisei/R04_chiho.html
          https://www.soumu.go.jp/main_content/000917808.xlsx
      令和5年度  : https://www.soumu.go.jp/menu_seisaku/toukei/02zaisei07_04000131.html
          https://www.soumu.go.jp/main_content/000983094.xlsx
      令和6年度  : https://www.soumu.go.jp/menu_seisaku/toukei/02zaisei07_04000135.html
          https://www.soumu.go.jp/main_content/001044529.xlsx
  (2) 地方財政状況調査 市町村別決算状況調  令和3〜6年度
      一覧ページ : https://www.soumu.go.jp/iken/kessan_jokyo_2.html
      令和3年度  : https://www.soumu.go.jp/iken/zaisei/r03_shichouson.html
          都市別 (1)概況          https://www.soumu.go.jp/main_content/000871018.xlsx
          都市別 (3)目的別歳出内訳 https://www.soumu.go.jp/main_content/000871020.xlsx
          町村別 (1)概況          https://www.soumu.go.jp/main_content/000871023.xlsx
          町村別 (3)目的別歳出内訳 https://www.soumu.go.jp/main_content/000871025.xlsx
      令和4年度  : https://www.soumu.go.jp/iken/zaisei/r04_shichouson.html
          都市別 (1)概況          https://www.soumu.go.jp/main_content/000937287.xlsx
          都市別 (3)目的別歳出内訳 https://www.soumu.go.jp/main_content/000937289.xlsx
          町村別 (1)概況          https://www.soumu.go.jp/main_content/000937292.xlsx
          町村別 (3)目的別歳出内訳 https://www.soumu.go.jp/main_content/000937294.xlsx
      令和5年度  : https://www.soumu.go.jp/iken/zaisei/r05_shichouson.html
          都市別 (1)概況          https://www.soumu.go.jp/main_content/000999900.xlsx
          都市別 (3)目的別歳出内訳 https://www.soumu.go.jp/main_content/000999902.xlsx
          町村別 (1)概況          https://www.soumu.go.jp/main_content/000999905.xlsx
          町村別 (3)目的別歳出内訳 https://www.soumu.go.jp/main_content/000999908.xlsx
      令和6年度  : https://www.soumu.go.jp/iken/zaisei/r06_shichouson.html
          都市別 (1)概況          https://www.soumu.go.jp/main_content/001061669.xlsx
          都市別 (3)目的別歳出内訳 https://www.soumu.go.jp/main_content/001061671.xlsx
          町村別 (1)概況          https://www.soumu.go.jp/main_content/001061674.xlsx
          町村別 (3)目的別歳出内訳 https://www.soumu.go.jp/main_content/001061676.xlsx

対象KPI（年度はPDFの値と照合して決定）:
  - 実質公債費比率       … (1) 令和3年度（和歌山市9.6でPDFと一致）
  - 財政力指数（類型）   … (1) 令和5年度（和歌山市0.77・岩出市0.61でPDFと一致）
  - 歳出総額の教育費割合 … (2) 令和3年度 教育費 ÷ 歳出総額（和歌山市7.19・田辺市7.39でPDFと一致）
  時系列比較用に令和3〜6年度（FY2021〜FY2024）の4か年分を取得する。

ファイルレイアウト（決算状況調）: 団体コード O列 / 概況の歳出総額(B) AO列 / 目的別の「十 教育費」BF列
  （令和3〜6年度で同一であることを確認済み）

取得日  : 2026-10-05（令和3・5年度分）、2026-10-06（令和4・6年度分を追加）
加工は行わず、公表ファイルをそのまま保存する。
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "04_data" / "01_raw" / "05_地方財政"

MC = "https://www.soumu.go.jp/main_content/"

# 全市町村の主要財政指標: 年度 -> ファイルID
SHIHYO = {"R03": "000849999", "R04": "000917808", "R05": "000983094", "R06": "001044529"}

# 市町村別決算状況調: 年度 -> (都市別01概況, 都市別03目的別, 町村別01概況, 町村別03目的別)
KESSAN = {
    "R03": ("000871018", "000871020", "000871023", "000871025"),
    "R04": ("000937287", "000937289", "000937292", "000937294"),
    "R05": ("000999900", "000999902", "000999905", "000999908"),
    "R06": ("001061669", "001061671", "001061674", "001061676"),
}
KESSAN_KINDS = ("都市別_01概況", "都市別_03目的別歳出内訳", "町村別_01概況", "町村別_03目的別歳出内訳")

FILES = {}
for fy, fid in SHIHYO.items():
    FILES[f"{fy}_全市町村の主要財政指標_{fid}.xlsx"] = f"{MC}{fid}.xlsx"
for fy, ids in KESSAN.items():
    for kind, fid in zip(KESSAN_KINDS, ids):
        FILES[f"{fy}_市町村別決算状況調_{kind}_{fid}.xlsx"] = f"{MC}{fid}.xlsx"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        (OUT / name).write_bytes(r.content)
        print(f"saved {name} ({len(r.content):,} bytes)")


if __name__ == "__main__":
    main()
