"""
04_住宅土地統計調査2023 ダウンロードスクリプト

- 統計名  : 令和5年住宅・土地統計調査 住宅及び世帯に関する基本集計（確報集計）
            全国・都道府県・市区町村
- 公表者  : 総務省統計局
- 公式ページ: https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200522&tstat=000001207800&cycle=0&tclass1=000001207808&tclass2=000001207809&layout=datalist&tclass3val=0
- 取得ファイル:
    表番号10-4 住宅の種類(2区分)、住宅の所有の関係(5区分)、建て方(4区分)別住宅数、世帯数、世帯人員、
    １住宅当たり居住室数、１住宅当たり居住室の畳数、１住宅当たり延べ面積、１人当たり居住室の畳数
    及び１室当たり人員－全国、都道府県、市区町村
    https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040209867&fileKind=0  (e010_4.xlsx)
- 対応KPI:
    - 一戸建の持ち家の割合（持ち家×一戸建の住宅数 / 住宅総数）
    - 住宅当たり延べ面積（１住宅当たり延べ面積）
- 注意    : 市区町村の集計対象は市・区及び人口1万5千人以上の町村のみ（調査仕様）
- 取得日  : 2026-10-05
"""
from pathlib import Path
import requests

OUT_DIR = Path(__file__).resolve().parents[2] / "04_data" / "01_raw" / "04_住宅土地統計調査2023"
FILES = {
    "e010_4.xlsx": "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040209867&fileKind=0",
}


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        (OUT_DIR / name).write_bytes(r.content)
        print(f"saved {name} ({len(r.content):,} bytes)")


if __name__ == "__main__":
    main()
