"""
09_経済センサス2021 ダウンロードスクリプト

- 統計名  : 令和3年経済センサス‐活動調査 事業所に関する集計 産業横断的集計 事業所数、従業者数
- 公表者  : 総務省統計局・経済産業省
- 公式ページ: https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200553&tstat=000001145590&cycle=0&tclass1=000001145649&tclass2=000001145667&tclass3=000001145670&layout=datalist&tclass4val=0
- 取得ファイル:
    表番号9-1A 産業(小分類)別全事業所数－全国、都道府県、市区町村
    https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040067884&fileKind=0  (b1_009_1a.xlsx)
- 対応KPI:
    - 人口あたり宗教の事業所数（産業中分類94「宗教」の事業所数、市区町村別。人口は別ソース）
- 調査時点: 2021年6月1日
- 取得日  : 2026-10-05
"""
from pathlib import Path
import requests

OUT_DIR = Path(__file__).resolve().parents[2] / "04_data" / "01_raw" / "09_経済センサス2021"
FILES = {
    "b1_009_1a.xlsx": "https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040067884&fileKind=0",
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
