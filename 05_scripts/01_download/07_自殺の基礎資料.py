"""07_自殺の基礎資料 : 厚生労働省「地域における自殺の基礎資料」（令和4年〜令和7年 確定値）をダウンロードする.

対象KPI
    人口あたり自殺者数（市区町村別・住居地ベース・各年確定値）

出典: 厚生労働省 社会・援護局 自殺対策推進室「地域における自殺の基礎資料」
公式ページ（年別）:
    令和4年: https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/seikatsuhogo/jisatsu/jisatsu_kiso_r4.html
    令和5年: https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/seikatsuhogo/jisatsu/jisatsu_kiso_r5.html
    令和6年: https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/seikatsuhogo/jisatsu/jisatsu_kiso_r6.html
    令和7年: https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/seikatsuhogo/jisatsu/jisatsu_kiso_r7.html
ファイル（確定値・自殺日集計）:
    令和4年: https://www.mhlw.go.jp/content/R4KAKUTEI-CHIIKI01.zip       （ページ上の表記は「令和４年確定値その１」= 自殺日集計）
    令和5年: https://www.mhlw.go.jp/content/12200000/001236396.zip  （令和５年自殺日集計）
    令和6年: https://www.mhlw.go.jp/content/001464821.zip           （令和６年自殺日集計）
    令和7年: https://www.mhlw.go.jp/content/001680831.zip           （令和７年自殺日集計）
    同梱: A7表(市町村・自殺日・住居地) ← 本KPIで使用
          A8表(市町村・自殺日・発見地)、A1-4表(全国)、A5/A6表(都道府県)、利用上の注意PDF
    ※ zipは公表されたまま保存し、同梱ファイルを年別サブフォルダ（R4_自殺日集計 等）へ展開する（内容の加工なし）。
    ※ zip内ファイル名の文字コードは年により異なる（R4〜R6: CP932 / R7: UTF-8フラグ付き）ため、
      UTF-8 → CP932 の順で解釈して展開する。

取得日: 2026-10-05（令和5年）、2026-10-06（令和4・6・7年）
"""

import io
import zipfile
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parents[2] / "04_data" / "01_raw" / "07_自殺の基礎資料"

# (和暦ラベル, URL, 保存zip名)
TARGETS = [
    ("R4", "https://www.mhlw.go.jp/content/R4KAKUTEI-CHIIKI01.zip",
     "R4_地域における自殺の基礎資料_自殺日集計_R4KAKUTEI-CHIIKI01.zip"),
    ("R5", "https://www.mhlw.go.jp/content/12200000/001236396.zip",
     "R5_地域における自殺の基礎資料_自殺日集計_001236396.zip"),
    ("R6", "https://www.mhlw.go.jp/content/001464821.zip",
     "R6_地域における自殺の基礎資料_自殺日集計_001464821.zip"),
    ("R7", "https://www.mhlw.go.jp/content/001680831.zip",
     "R7_地域における自殺の基礎資料_自殺日集計_001680831.zip"),
]


def open_zip(content: bytes) -> zipfile.ZipFile:
    """zip内ファイル名を UTF-8 → CP932 の順で解釈して開く."""
    for enc in ("utf-8", "cp932"):
        try:
            return zipfile.ZipFile(io.BytesIO(content), metadata_encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("zip内ファイル名の文字コードを判別できません")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for label, url, zip_name in TARGETS:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=120)
        resp.raise_for_status()
        (OUT_DIR / zip_name).write_bytes(resp.content)
        print(f"saved {zip_name} ({len(resp.content):,} bytes) <- {url}")

        extract_dir = OUT_DIR / f"{label}_自殺日集計"
        extract_dir.mkdir(exist_ok=True)
        with open_zip(resp.content) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = Path(info.filename).name
                (extract_dir / name).write_bytes(z.read(info))
                print(f"  extracted {extract_dir.name}/{name}")


if __name__ == "__main__":
    main()
