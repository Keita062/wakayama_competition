"""06_健康寿命 : 健康寿命（近似）算出用の原データ3種をダウンロードする.

対象KPI
    健康寿命（男性）・健康寿命（女性）［市区町村別・近似］
    ※ サリバン法等で算出するための原データ（人口・生命表・要介護認定者数）を取得する。加工はしない。

取得日: 2026-10-05

① 総務省「住民基本台帳に基づく人口、人口動態及び世帯数調査」
    令和6年1月1日現在 【総計】市区町村別年齢階級別人口（男女別・5歳階級）
    公式ページ: https://www.soumu.go.jp/main_sosiki/jichi_gyousei/daityo/jinkou_jinkoudoutai-setaisuu.html
    e-Stat: https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&year=20240&toukei=00200241&tstat=000001039591&cycle=7&tclass1=000001039601&tclass2val=0
    ファイル: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040306674&fileKind=0  (2404ssnen.xlsx)

② 厚生労働省「令和2年市区町村別生命表」（全1,887市区町村の完全な生命表：nqx, lx, ndx, nLx, Tx, ex／男女別）
    公式ページ: https://www.mhlw.go.jp/toukei/saikin/hw/life/ckts20/index.html
    e-Stat: https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00450012&tstat=000001031336&cycle=7&tclass1=000001060926&tclass2=000001204500&layout=datalist&tclass3val=0
    ファイル: https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040052725&fileKind=0  (ckts-lifetable2020.xlsx)

③ 厚生労働省「介護保険事業状況報告（暫定）令和6年6月分」月報 保険者別
    公式ページ: https://www.mhlw.go.jp/topics/kaigo/osirase/jigyo/m24/2406.html
    ファイル:
      https://www.mhlw.go.jp/topics/kaigo/osirase/jigyo/m24/xls/2406-h1.xlsx    第1表 保険者別 第1号被保険者数（年齢3区分）
      https://www.mhlw.go.jp/topics/kaigo/osirase/jigyo/m24/xls/2406-h2-1.xlsx  第2-1表 保険者別 要介護（要支援）認定者数 男女計
      https://www.mhlw.go.jp/topics/kaigo/osirase/jigyo/m24/xls/2406-h2-2.xlsx  第2-2表 同 男（第1号は5歳階級別再掲あり）
      https://www.mhlw.go.jp/topics/kaigo/osirase/jigyo/m24/xls/2406-h2-3.xlsx  第2-3表 同 女
"""

import re
from pathlib import Path
from urllib.parse import unquote

import requests

OUT_DIR = Path(__file__).resolve().parents[2] / "04_data" / "01_raw" / "06_健康寿命"
HEADERS = {"User-Agent": "Mozilla/5.0"}

ESTAT = "https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind=0"
KAIGO = "https://www.mhlw.go.jp/topics/kaigo/osirase/jigyo/m24/xls/{}"

# (URL, 保存ファイル名 or None=サーバ提供のファイル名)
FILES = [
    (ESTAT.format("000040306674"), None),  # ① 住基 R6.1.1 市区町村別年齢階級別人口（総計）
    (ESTAT.format("000040052725"), None),  # ② 令和2年市区町村別生命表
    (KAIGO.format("2406-h1.xlsx"), "2406-h1.xlsx"),  # ③ 第1号被保険者数（保険者別）
    (KAIGO.format("2406-h2-1.xlsx"), "2406-h2-1.xlsx"),  # ③ 認定者数 男女計
    (KAIGO.format("2406-h2-2.xlsx"), "2406-h2-2.xlsx"),  # ③ 認定者数 男
    (KAIGO.format("2406-h2-3.xlsx"), "2406-h2-3.xlsx"),  # ③ 認定者数 女
]


def filename_from_response(resp: requests.Response) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search(r'filename="?([^";]+)', cd)
    if not m:
        raise RuntimeError(f"ファイル名を取得できません: {resp.url}")
    return unquote(m.group(1))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for url, name in FILES:
        resp = requests.get(url, headers=HEADERS, timeout=120)
        resp.raise_for_status()
        if resp.content[:15].lstrip().lower().startswith(b"<!doctype html"):
            raise RuntimeError(f"HTMLが返されました: {url}")
        name = name or filename_from_response(resp)
        path = OUT_DIR / name
        path.write_bytes(resp.content)
        print(f"saved {path.name} ({len(resp.content):,} bytes) <- {url}")


if __name__ == "__main__":
    main()
