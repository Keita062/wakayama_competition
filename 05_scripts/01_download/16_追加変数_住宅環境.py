"""16_追加変数_住宅環境 ダウンロードスクリプト

目的    : 和歌山市の重点分野「住宅環境」（主観スコア）を、個別KPI（一戸建の持ち家の割合・住宅当たり延べ面積。
          どちらも施策で動かせない）以外で説明しうる追加変数を、全国の市区町村について公的オープンデータ
          （1ファイルで全国の市区町村を収録したもの）から集める。施策で動かせる変数を重視する。

住宅環境の主観指標（設問）: デジタル庁「地域幸福度（Well-Being）指標」指標構成元データ（市区町村版）
    https://well-being.digital.go.jp/guide （guidebook_sources_municipalities.xlsx の「住宅環境」シート。
    手元の 00_context/guidebook_sources_municipalities.xlsx と同じ）
      1 自宅には、心地のいい居場所がある
      2 【点数逆転設問】自宅の近辺は、騒音に悩まされている
      3 私の暮らしている地域では、適度な費用で住居を確保できる

出典・公式ページ・取得ファイル（加工なしの原本）:

① 令和5年住宅・土地統計調査 住宅及び世帯に関する基本集計（確報集計）（総務省統計局）e-Stat
   公式ページ（04_住宅土地統計調査2023.py と同じ）:
   https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00200522&tstat=000001207800&cycle=0&tclass1=000001207808&tclass2=000001207809&layout=datalist&tclass3val=0
   ※ 市区町村の集計対象は市・区及び人口1万5千人以上の町村のみ（調査仕様）。対象外の町村は欠損。
    e001_2.xlsx  第1-2表 居住世帯の有無(8区分)別住宅数及び住宅以外で人が居住する建物数－全国、都道府県、市区町村
                 statInfId=000040209842 → 賃貸・売却用及び二次的住宅を除く空き家の割合  [2023年10月1日]
    e005_3.xlsx  第5-3表 住宅の所有の関係(5区分)、建築の時期(7区分)別住宅数－全国、都道府県、市区町村
                 statInfId=000040209851 → 1980年以前に建築された住宅の割合（旧耐震基準）
    e025_3.xlsx  第25-3表 住宅の種類(2区分)、住宅の所有の関係(2区分)、高齢者等のための設備状況(14区分)別住宅数
                 －全国、都道府県、市区町村  statInfId=000040209886 → 高齢者等のための設備がある住宅の割合
    e030_2.xlsx  第30-2表 住宅の種類(2区分)、住宅の所有の関係(2区分)、建築の時期(9区分)、省エネルギー設備等(7区分)別住宅数
                 －全国、都道府県、市区町村  statInfId=000040209893 → 二重サッシ・複層ガラスの窓がある住宅の割合
    e032_2.xlsx  第32-2表 住宅の所有の関係(6区分)、腐朽・破損の有無(2区分)、建築の時期(9区分)別住宅数
                 －全国、都道府県、市区町村  statInfId=000040209896 → 腐朽・破損のある住宅の割合
    e036.xlsx    第36表 腐朽・破損の有無(2区分)、2019年以降の住宅の増改築・改修工事等(8区分)別持ち家数
                 －全国、都道府県、市区町村  statInfId=000040209903 → 2019年以降に増改築・改修工事をした持ち家の割合
    e122_4.xlsx  第122-4表 住宅の所有の関係(4区分)別延べ面積１平方メートル当たり家賃(10区分)別借家(専用住宅)数
                 及び延べ面積１平方メートル当たり家賃－全国、都道府県、市区町村
                 statInfId=000040210062 → 民営借家の延べ面積1m²当たり家賃
   取得URL: https://www.e-stat.go.jp/stat-search/file-download?statInfId={statInfId}&fileKind=0

② 国土数値情報 地価調査データ（L02、国土交通省。都道府県地価調査の基準地。各年7月1日時点）
   公式ページ: https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L02-2025.html
    L02-22_GML.zip  https://nlftp.mlit.go.jp/ksj/gml/data/L02/L02-22/L02-22_GML.zip  [2022年]
    L02-23_GML.zip  https://nlftp.mlit.go.jp/ksj/gml/data/L02/L02-23/L02-23_GML.zip  [2023年]
    L02-24_GML.zip  https://nlftp.mlit.go.jp/ksj/gml/data/L02/L02-24/L02-24_GML.zip  [2024年]
    L02-25_GML.zip  https://nlftp.mlit.go.jp/ksj/gml/data/L02/L02-25/L02-25_GML.zip  [2025年]
    → 住宅地の基準地の平均価格（円/m²）。地域幸福度の客観指標「平均価格（住宅地）」と同じ出典

再ダウンロードしないもの（手元の原本を使う）:
  12_公共施設状況調/市町村経年比較表_H18-R06_001068878.xlsx（総務省「公共施設状況調経年比較表」、各年度3月31日現在）
    → 市町村営の公営住宅等の戸数（公営住宅＋改良住宅＋単独住宅）、公共下水道の現在処理区域内人口
  06_健康寿命/YYMMssnen.xlsx（住民基本台帳人口。分母）

取れなかったもの:
  サービス付き高齢者向け住宅の戸数：サ高住情報提供システム（https://www.satsuki-jutaku.mlit.go.jp/）の登録状況の
    集計表は都道府県別のみ。市区町村別は物件検索の個票しかなく、1ファイルで全国の市区町村が分かる公的ファイルがない。
  耐震改修の実施割合：令和5年住宅・土地統計調査の市区町村別の表に「耐震改修工事」の区分がない
    （第36表の区分は「壁・柱・基礎等の補強工事」まで）。第36表の改修工事全体の割合で代える。
  高齢者のいる世帯の住宅のバリアフリー化率：65歳以上の世帯員のいる世帯×高齢者等のための設備の表（第46表）は全国のみ。
    市区町村別は全住宅についての第25-3表で代える。
  汚水処理人口普及率（下水道＋集落排水＋浄化槽）：国の「全国市町村別 汚水処理人口普及率一覧」（環境省報道資料の参考資料
    https://www.env.go.jp/content/000335185.pdf ）は画像のPDFで読み取れない。公共施設状況調の合併処理浄化槽の処理人口は
    計上漏れとみられる値（普及率0%の町村など）があるため、公共下水道の処理人口普及率だけを使う。
  騒音（設問2）：道路交通騒音の環境基準達成状況・公害苦情（騒音）件数は、全国の市区町村を1ファイルで収録した公的ファイルがない。

取得日  : 2026-10-07
"""
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[2]
OUT_DIR = BASE / "04_data" / "01_raw" / "16_追加変数_住宅環境"

HEADERS = {"User-Agent": "Mozilla/5.0"}
ESTAT = "https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind=0"
KSJ = "https://nlftp.mlit.go.jp/ksj/gml/data/L02/L02-{0}/L02-{0}_GML.zip"
FILES = {
    "e001_2.xlsx": ESTAT.format("000040209842"),   # 住宅・土地統計調査2023 第1-2表（空き家）
    "e005_3.xlsx": ESTAT.format("000040209851"),   # 第5-3表（建築の時期）
    "e025_3.xlsx": ESTAT.format("000040209886"),   # 第25-3表（高齢者等のための設備）
    "e030_2.xlsx": ESTAT.format("000040209893"),   # 第30-2表（省エネルギー設備等）
    "e032_2.xlsx": ESTAT.format("000040209896"),   # 第32-2表（腐朽・破損）
    "e036.xlsx": ESTAT.format("000040209903"),     # 第36表（増改築・改修工事）
    "e122_4.xlsx": ESTAT.format("000040210062"),   # 第122-4表（延べ面積1m²当たり家賃）
    "L02-22_GML.zip": KSJ.format(22),              # 国土数値情報 地価調査 2022年
    "L02-23_GML.zip": KSJ.format(23),              # 2023年
    "L02-24_GML.zip": KSJ.format(24),              # 2024年
    "L02-25_GML.zip": KSJ.format(25),              # 2025年
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
