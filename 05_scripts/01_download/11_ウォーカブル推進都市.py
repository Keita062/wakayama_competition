"""11_ウォーカブル推進都市 ダウンロード

- データ名: ウォーカブル推進都市 推進都市一覧（2026.8.31現在, 402都市）
- 作成機関: 国土交通省 都市局（まちづくり推進課／街路交通施設課）
- 公式ページ: https://www.mlit.go.jp/toshi/toshi_gairo_tk_000081.html
- ファイルURL: https://www.mlit.go.jp/toshi/content/002019449.pdf  （PDF。毎月月末に更新され URL も変わるため、
    スクリプトでは公式ページの「推進都市一覧」リンクを都度取得する。見つからなければ上記URLを使う）
    ※PDFにはウォーカブル区域（滞在快適性等向上区域）設定の有無も記載
- 対象KPI : ウォーカブル推進都市（市区町村ごとの 0/1 フラグ）
- 取得日  : 2026-10-05
"""
import re
from pathlib import Path
from urllib.parse import urljoin

import requests

OUT_DIR = Path(__file__).resolve().parents[2] / "04_data" / "01_raw" / "11_ウォーカブル推進都市"
PAGE = "https://www.mlit.go.jp/toshi/toshi_gairo_tk_000081.html"
FALLBACK = "https://www.mlit.go.jp/toshi/content/002019449.pdf"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page = requests.get(PAGE, timeout=60)
    page.encoding = page.apparent_encoding
    m = re.search(r'href="([^"]+\.pdf)"[^>]*>\s*推進都市一覧（([^）]+)）', page.text)
    url, asof = (urljoin(PAGE, m.group(1)), m.group(2)) if m else (FALLBACK, "2026.8.31現在")
    print(f"list url: {url} ({asof})")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    out = OUT_DIR / f"ウォーカブル推進都市一覧_{asof.replace('現在', '')}_{Path(url).name}"
    out.write_bytes(r.content)
    print(f"saved {out.name} ({len(r.content):,} bytes)")


if __name__ == "__main__":
    main()
