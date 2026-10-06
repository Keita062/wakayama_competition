"""都市モニタリングシート（全体表）ダウンロード

- ソース名 : 都市モニタリングシート【全体表】（全国1,700超の市区町村 × 約400指標, Excel）
- 公表元   : 国土交通省 都市局 都市計画課
- 公式ページ:
    https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000036.html （ダウンロードページ）
    https://www.mlit.go.jp/toshi/tosiko/toshi_tosiko_tk_000035.html （概要・データ定義書）
- ファイルURL:
    https://www.mlit.go.jp/toshi/tosiko/content/001406670.xlsx  （全体表）
    https://www.mlit.go.jp/toshi/tosiko/content/001379896.pdf   （収録データ定義書：指標定義・出典年次の確認用）
- 対象KPI:
    医療施設徒歩圏人口カバー率 / 福祉施設徒歩圏人口カバー率 / 商業施設徒歩圏人口カバー率 /
    駅・バス停留所徒歩圏人口カバー率 / 公園緑地徒歩圏人口カバー率 / 保育所徒歩圏0〜4歳人口カバー率 /
    人口あたり小型車走行キロ / 歩道設置率
- 取得日   : 2026-10-05
- 加工なし（公表ファイルをそのまま保存）
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "04_data" / "01_raw" / "01_都市モニタリングシート"

FILES = {
    "都市モニタリングシート_全体表_001406670.xlsx": "https://www.mlit.go.jp/toshi/tosiko/content/001406670.xlsx",
    "都市モニタリングシート_収録データ定義書_001379896.pdf": "https://www.mlit.go.jp/toshi/tosiko/content/001379896.pdf",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=300)
        r.raise_for_status()
        (OUT / name).write_bytes(r.content)
        print(f"saved {name} ({len(r.content):,} bytes)")


if __name__ == "__main__":
    main()
