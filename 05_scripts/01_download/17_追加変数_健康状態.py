"""17_追加変数_健康状態 ダウンロードスクリプト

目的    : 田辺市の重点分野「健康状態」（主観。設問「私は、身体的に健康な状態である」「私は、精神的に健康な状態である」）
          を、既存の個別KPI（健康寿命の近似値。施策で動かせない）以外で説明しうる変数を、全国の市区町村について
          公的オープンデータ（1ファイルで全国の市区町村を収録したもの）から集める。施策で動かせる変数を重視する。
          手元の 04_data/01_raw 配下で足りるもの（下の「再ダウンロードしないもの」）は取得しない。

出典・公式ページ・取得ファイル（加工なしの原本）:

① 厚生労働省「特定健康診査・特定保健指導の実施状況（保険者別）」（市町村国保は「国民健康保険」シート, 1,738保険者）
   一覧ページ https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000161103.html
    特定健診_2022.xlsx  2022年度 https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/newpage_00045.html
                        https://www.mhlw.go.jp/content/12400000/001251479.xlsx
    特定健診_2023.xlsx  2023年度 https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/newpage_00063.html
                        https://www.mhlw.go.jp/content/12400000/001520593.xlsx
    → 特定健康診査の対象者数・受診者数（実施率）、特定保健指導の対象者数・終了者数（実施率）
   ※ 2024年度分のページ（newpage_00084.html）は取得日時点で「掲載一時中止」のため取得できない。

② 厚生労働省「地域保健・健康増進事業報告」健康増進編 第２章 市区町村表（e-Stat, CSV）
   e-Stat https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00450025&tstat=000001030884
     令和6年度 tclass1=000001241336&tclass2=000001241338&tclass3=000001241343
     令和5年度 tclass1=000001227363&tclass2=000001227368&tclass3=000001227370
     令和4年度 tclass1=000001216080&tclass2=000001216085&tclass3=000001216087
   第20-1表 健康診査、肺がん検診及び大腸がん検診対象者数・受診者数・受診率・（再掲）国民健康保険の被保険者，市区町村、種類別
    がん検診_R04.csv  statInfId=000040165455  [2022年度]
    がん検診_R05.csv  statInfId=000040262026  [2023年度]
    がん検診_R06.csv  statInfId=000040423652  [2024年度]
    → 大腸がん検診の対象者数・受診者数・受診率（40〜69歳、国保被保険者の再掲）
   第３表 集団健康教育の開催回数・参加延人員，市区町村、教育内容別
    健康教育_R04.csv  statInfId=000040165404  [2022年度]
    健康教育_R05.csv  statInfId=000040261975  [2023年度]
    健康教育_R06.csv  statInfId=000040423599  [2024年度]
    → 集団健康教育の参加延人員（総数）
   URL: https://www.e-stat.go.jp/stat-search/file-download?statInfId={statInfId}&fileKind=1

③ 厚生労働省「医療費の地域差分析」基礎データ 表30 市区町村別データ（市町村国民健康保険）
   公式ページ https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryouhoken/database/iryomap/index.html
    医療費地域差_R04.xlsx  https://www.mhlw.go.jp/content/iryohi_r04_kiso.xlsx  [2022年度]
    医療費地域差_R05.xlsx  https://www.mhlw.go.jp/content/iryohi_r05_kiso.xlsx  [2023年度]
    → 地域差指数（一人当たり年齢調整後医療費。計）
   ※ 令和6年度は「電算処理分」の基礎データ（iryohi_r06den_kiso.xlsx）のみ公表で、市区町村別の表がないため取得しない。

④ 社会・人口統計体系「統計でみる市区町村のすがた」（総務省統計局）e-Stat  I 健康・医療
   公式ページは 03_社会人口統計体系.py と同じ（すがた2026 tstat=000001244297 / 2025 tstat=000001229545）。
   statInfId は各版の B ファイル（取得済み）と連番であることを e-Stat 上で確認（I=B+7）。
    2026-i.xls  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040463592&fileKind=0
                → 一般診療所数(I5102) [2023年], 医師数(I6100) [2022年]
    2025-i.xls  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040283818&fileKind=0
                → 一般診療所数(I5102) [2022年]
   ※ 各版の収録データ年はファイル10行目（0始まり9行目）の年次欄で確認済み。すがた2024（2024-i.xls）は
     一般診療所数が2021年・医師数が2020年で、データ年2022〜2025の範囲外のため取得しない。

再ダウンロードしないもの（手元の原本を使う）:
  06_健康寿命/YYMMssnen.xlsx      → 住基人口（男65〜74歳、40歳以上、総人口）
  06_健康寿命/YY06-h2-2.xlsx      → 介護保険事業状況報告 月報（各年6月末）第2-2表 男の要介護（要支援）認定者数
                                     （第1号の65〜69歳・70〜74歳の再掲）
  14_追加変数/通いの場_R0N.xlsx   → 通いの場（03_追加変数.csv に作成済みのため再作成もしない）

取れなかったもの:
  シルバー人材センター会員数：全国シルバー人材センター事業協会の「全国統計」（https://www.zsjc.or.jp/toukei/list_page）は
    全国計（1ページPDF）のみで、センター別の会員数は検索画面で1センターずつ表示する形式。全国の市区町村が1ファイルに
    まとまった公表がないため取得しない。
  65歳以上の運動習慣・スポーツ実施率：NDBオープンデータ（特定健診の質問票）は都道府県・二次医療圏単位、
    スポーツ庁の調査は全国・都道府県単位で、市区町村別の公的オープンデータがないため取得しない。

取得日  : 2026-10-07
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT_DIR = BASE / "04_data" / "01_raw" / "17_追加変数_健康状態"

HEADERS = {"User-Agent": "Mozilla/5.0"}
ESTAT = "https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind={}"
FILES = {
    "特定健診_2022.xlsx": "https://www.mhlw.go.jp/content/12400000/001251479.xlsx",   # 特定健診・保健指導 保険者別 2022年度
    "特定健診_2023.xlsx": "https://www.mhlw.go.jp/content/12400000/001520593.xlsx",   # 同 2023年度
    "がん検診_R04.csv": ESTAT.format("000040165455", 1),   # 地域保健・健康増進事業報告 第20-1表 2022年度
    "がん検診_R05.csv": ESTAT.format("000040262026", 1),   # 同 2023年度
    "がん検診_R06.csv": ESTAT.format("000040423652", 1),   # 同 2024年度
    "健康教育_R04.csv": ESTAT.format("000040165404", 1),   # 地域保健・健康増進事業報告 第3表 2022年度
    "健康教育_R05.csv": ESTAT.format("000040261975", 1),   # 同 2023年度
    "健康教育_R06.csv": ESTAT.format("000040423599", 1),   # 同 2024年度
    "医療費地域差_R04.xlsx": "https://www.mhlw.go.jp/content/iryohi_r04_kiso.xlsx",   # 医療費の地域差分析 2022年度
    "医療費地域差_R05.xlsx": "https://www.mhlw.go.jp/content/iryohi_r05_kiso.xlsx",   # 同 2023年度
    "2026-i.xls": ESTAT.format("000040463592", 0),   # すがた2026 I 健康・医療（診療所 2023年, 医師 2022年）
    "2025-i.xls": ESTAT.format("000040283818", 0),   # すがた2025 I 健康・医療（診療所 2022年）
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        r = requests.get(url, timeout=600, headers=HEADERS)
        r.raise_for_status()
        path = OUT_DIR / name
        path.write_bytes(r.content)
        print(f"saved {path.name} ({len(r.content):,} bytes) <- {url}")


if __name__ == "__main__":
    main()
