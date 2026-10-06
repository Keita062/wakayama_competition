"""07_自殺の基礎資料 : 厚生労働省「地域における自殺の基礎資料（令和5年）」をダウンロードする.

対象KPI
    人口あたり自殺者数（市区町村別・住居地ベース・令和5年確定値）

出典: 厚生労働省 社会・援護局 自殺対策推進室「地域における自殺の基礎資料」
公式ページ: https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/seikatsuhogo/jisatsu/jisatsu_kiso_r5.html
ファイル: https://www.mhlw.go.jp/content/12200000/001236396.zip  （令和5年自殺日集計）
    同梱: A7表(市町村・自殺日・住居地) ← 本KPIで使用
          A8表(市町村・自殺日・発見地)、A1-4表(全国)、A5/A6表(都道府県)、利用上の注意PDF
    ※ zipは公表されたまま保存し、同梱ファイルを同名サブフォルダへ展開する（内容の加工なし）。

取得日: 2026-10-05
"""

import io
import zipfile
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parents[2] / "04_data" / "01_raw" / "07_自殺の基礎資料"
URL = "https://www.mhlw.go.jp/content/12200000/001236396.zip"
ZIP_NAME = "R5_地域における自殺の基礎資料_自殺日集計_001236396.zip"
EXTRACT_DIR = OUT_DIR / "R5_自殺日集計"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resp = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
    resp.raise_for_status()
    (OUT_DIR / ZIP_NAME).write_bytes(resp.content)
    print(f"saved {ZIP_NAME} ({len(resp.content):,} bytes) <- {URL}")

    EXTRACT_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        for info in z.infolist():
            name = info.filename  # 本zipはファイル名がUTF-8で格納されている
            (EXTRACT_DIR / Path(name).name).write_bytes(z.read(info))
            print(f"  extracted {Path(name).name}")


if __name__ == "__main__":
    main()
