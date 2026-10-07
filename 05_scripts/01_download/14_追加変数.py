"""14_追加変数 ダウンロードスクリプト

目的    : 「地域とのつながり」「自己効力感」を個別KPIで説明できなかったため、説明候補の追加変数を
          全国の市区町村について公的オープンデータ（1ファイルで全国の市区町村を収録したもの）から集める。
          手元の 04_data/01_raw 配下で足りるもの（下の「再ダウンロードしないもの」）は取得しない。

出典・公式ページ・取得ファイル（加工なしの原本）:

① 令和2年国勢調査（総務省統計局）e-Stat
  - 移動人口の男女・年齢等集計 https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200521&tstat=000001136464
    f08_01.xlsx  第8-1表 男女，居住期間，5年前の常住地別人口－全国，都道府県，市区町村（現住地）
                 https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032168622&fileKind=0
                 → 居住期間20年以上の人口割合  [2020年10月1日]
  - 人口等基本集計 https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200521&tstat=000001136464&cycle=0&tclass1=000001136466&layout=datalist&tclass2val=0
    b19_04.xlsx  第19-4表 住宅の所有の関係，住宅の建て方・世帯が住んでいる階別一般世帯数－全国，都道府県，市区町村
                 https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032142552&fileKind=0
                 → 共同住宅に住む一般世帯の割合  [2020年]
  - 就業状態等基本集計 https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200521&tstat=000001136464&cycle=0&tclass1=000001136467&layout=datalist&tclass2val=0
    c03_02.xlsx  第3-2表 男女，従業上の地位別就業者数（15歳以上）－全国，都道府県，市区町村
                 https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032201198&fileKind=0
                 → 雇用者に占める正規の職員・従業員の割合  [2020年]
    c11_02.xlsx  第11-2表 男女，年齢（5歳階級），在学か否かの別・最終卒業学校の種類別人口（15歳以上）－全国，都道府県，市区町村
                 https://www.e-stat.go.jp/stat-search/file-download?statInfId=000032201217&fileKind=0
                 → 大学・大学院卒業者の割合  [2020年]

② 社会・人口統計体系「統計でみる市区町村のすがた」（総務省統計局）e-Stat
   公式ページは 03_社会人口統計体系.py と同じ（すがた2026 tstat=000001244297 / 2025 tstat=000001229545 / 2024 tstat=000001218560）。
   statInfId は各版の B・E ファイル（取得済み）と連番であることを e-Stat 上で確認（A=B−1, C=B+1, F=B+4）。
    2026-a.xls  A 人口・世帯  https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040463584&fileKind=0
                → 総人口(A1101)・昼間人口(A6107)  [2020年]（昼夜間人口比率）
    2026-f.xls  F 労働        https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040463589&fileKind=0
                → 就業者数(F1102)・他市区町村への通勤者数(F2705)  [2020年]
    2026-c.xls  C 経済基盤    https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040463586&fileKind=0
                → 課税対象所得(C120110)・納税義務者数(所得割)(C120120)  [2024年]
    2025-c.xls  C 経済基盤    https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040283812&fileKind=0
                → 同上  [2023年]
    2024-c.xls  C 経済基盤    https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040186223&fileKind=0
                → 同上  [2022年]
   ※ 各版の収録データ年はファイル10行目（0始まり9行目）の年次欄で確認済み。
   ※ G 文化・スポーツ（YYYY-g.xls）は公民館数・図書館数（2021年、社会教育調査）の2項目のみで、全版とも同じ2021年値。
     社会体育施設数は収録されていない。同じ公民館・図書館数（市町村立）と体育施設数を年度ごとに持つ
     手元の 12_公共施設状況調（市町村経年比較表）を使うため、G は取得しない。

③ 令和3年経済センサス‐活動調査（総務省・経済産業省）e-Stat
   https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200553&tstat=000001145590&cycle=0&tclass1=000001145649&tclass2=000001145667&tclass3=000001145670&layout=datalist&tclass4val=0
    b1_030.xlsx  第30表 存続・新設・廃業別民営事業所数及び男女別従業者数－全国、都道府県、郡・支庁等、市区町村
                 https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040067937&fileKind=0
                 → 新設事業所数（2016年経済センサス‐活動調査以降に新設）  [2021年6月1日]
   ※ 第24表（開設時期別, statInfId=000040067928, 59MB）も市区町村別だが、新設事業所数は第30表で足りるため取得しない。

④ 厚生労働省「介護予防・日常生活支援総合事業（地域支援事業）の実施状況に関する調査結果」
   Ⅱ（令和6年度はⅠ）介護予防に資する住民主体の通いの場の展開状況 市町村別（全1,741市町村）
    公式ページ: 令和6年度 https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/r6sogojigyo_surveyresults_00003.html
                令和5年度 https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/r5sogojigyo_surveyresults.html
                令和4年度 （介護予防のページ https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/kaigo_koureisha/yobou/index.html
                            から個別ページへのリンクなし。令和5年度と同じ命名規則のファイルが公開されている）
    通いの場_R04.xlsx  https://www.mhlw.go.jp/content/12300000/R4survey_2_shichouson.xlsx  [2022年度]
    通いの場_R05.xlsx  https://www.mhlw.go.jp/content/12300000/R5survey_2_shichouson.xlsx  [2023年度]
    通いの場_R06.xlsx  https://www.mhlw.go.jp/content/12300000/001730264.xlsx            [2024年度]
    → 通いの場の箇所数（計）・参加者実人数（計）
   ※ 令和7年度実施分は取得日時点で未公表。

⑤ 総務省「地域おこし協力隊の隊員数等について」（報道資料。市町村別隊員数の一覧「活躍先」を含むPDF）
    公式ページ: 令和7年度 https://www.soumu.go.jp/menu_news/s-news/01gyosei08_02000325.html
                令和4年度 https://www.soumu.go.jp/menu_news/s-news/01gyosei08_02000252.html
    協力隊_R04.pdf  https://www.soumu.go.jp/main_content/000873869.pdf  [2022年度 特交ベース, 隊員6,447人]
    協力隊_R05.pdf  https://www.soumu.go.jp/main_content/000941085.pdf  [2023年度, 7,200人]
    協力隊_R06.pdf  https://www.soumu.go.jp/main_content/001002966.pdf  [2024年度, 7,910人]
    協力隊_R07.pdf  https://www.soumu.go.jp/main_content/001070453.pdf  [2025年度, 8,196人]
    → 市町村別隊員数（一覧に載っていない市町村は0人）

再ダウンロードしないもの（手元の原本を使う）:
  02_国勢調査2020/c01_02.xlsx        → 就業率・女性就業率・65歳以上就業率
  06_健康寿命/YYMMssnen.xlsx         → 住基人口（20〜39歳人口割合、各分母、65歳以上人口）
  08_住民基本台帳人口移動報告/b01103s → 20〜39歳の転入超過数（5歳階級）
  09_経済センサス2021/b1_009_1a.xlsx  → 中分類93 政治・経済・文化団体の事業所数
  12_公共施設状況調/市町村経年比較表 → 公民館・図書館・体育施設・集会施設の箇所数（市町村立, 各年度）

取れなかったもの:
  衆議院議員総選挙の市区町村別投票率：総務省「結果調」は都道府県別の投票率と、都道府県ごとの
  候補者別市区町村別「得票数」ファイル（有権者数・投票者数なし）しかなく、1ファイルで全国の市区町村の
  投票率が分かる公的ファイルがないため取得しない。

取得日  : 2026-10-06
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT_DIR = BASE / "04_data" / "01_raw" / "14_追加変数"

HEADERS = {"User-Agent": "Mozilla/5.0"}
ESTAT = "https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind=0"
FILES = {
    "f08_01.xlsx": ESTAT.format("000032168622"),   # 国勢調査2020 移動人口 第8-1表（居住期間）
    "b19_04.xlsx": ESTAT.format("000032142552"),   # 国勢調査2020 人口等基本 第19-4表（住宅の建て方）
    "c03_02.xlsx": ESTAT.format("000032201198"),   # 国勢調査2020 就業状態等 第3-2表（従業上の地位）
    "c11_02.xlsx": ESTAT.format("000032201217"),   # 国勢調査2020 就業状態等 第11-2表（最終卒業学校）
    "2026-a.xls": ESTAT.format("000040463584"),    # すがた2026 A 人口・世帯（昼間人口 2020年）
    "2026-f.xls": ESTAT.format("000040463589"),    # すがた2026 F 労働（他市区町村への通勤者 2020年）
    "2026-c.xls": ESTAT.format("000040463586"),    # すがた2026 C 経済基盤（課税対象所得 2024年）
    "2025-c.xls": ESTAT.format("000040283812"),    # すがた2025 C 経済基盤（2023年）
    "2024-c.xls": ESTAT.format("000040186223"),    # すがた2024 C 経済基盤（2022年）
    "b1_030.xlsx": ESTAT.format("000040067937"),   # 経済センサス‐活動調査2021 第30表（新設事業所）
    "通いの場_R04.xlsx": "https://www.mhlw.go.jp/content/12300000/R4survey_2_shichouson.xlsx",
    "通いの場_R05.xlsx": "https://www.mhlw.go.jp/content/12300000/R5survey_2_shichouson.xlsx",
    "通いの場_R06.xlsx": "https://www.mhlw.go.jp/content/12300000/001730264.xlsx",
    "協力隊_R04.pdf": "https://www.soumu.go.jp/main_content/000873869.pdf",
    "協力隊_R05.pdf": "https://www.soumu.go.jp/main_content/000941085.pdf",
    "協力隊_R06.pdf": "https://www.soumu.go.jp/main_content/001002966.pdf",
    "協力隊_R07.pdf": "https://www.soumu.go.jp/main_content/001070453.pdf",
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
