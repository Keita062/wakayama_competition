"""「住宅環境」（主観スコア）の説明候補となる追加変数を、市区町村 × 年度版の表にまとめる。

入力 : 04_data/01_raw/16_追加変数_住宅環境/（05_scripts/01_download/16_追加変数_住宅環境.py で取得）
       手元の原本 02_国勢調査2020/b02_07.xlsx（政令市の区→市）, 06_健康寿命/YYMMssnen.xlsx（住基人口）,
       12_公共施設状況調/市町村経年比較表
       行の土台：04_data/02_processed/01_市区町村別_個別KPI.csv（1,741市区町村）
出力 : 04_data/02_processed/05_追加変数_住宅環境.csv（市区町村コード, 年度版, 各変数）
       04_data/02_processed/05_追加変数_住宅環境_定義.csv（03_追加変数_定義.csv の列 ＋ 操作可能性・操作可能性の理由）

住宅環境の主観指標（設問）: 1 自宅には、心地のいい居場所がある／2【逆転】自宅の近辺は、騒音に悩まされている／
                            3 私の暮らしている地域では、適度な費用で住居を確保できる

行・年度版・分母・政令市の扱いは 03_追加変数の作成.py と同じ:
  行   : 全国の市区町村（政令市は市全体の1行、東京23区は区ごと）＝1,741 × 年度版4（2023〜2026）
  年度版: 「年度版Y ← Y−1年（暦年・年度）の値」。未公表の年は最も近い前の年で代用し「代用」に記録。1時点の変数は全年度版に同じ値。
  分母 : 年ごとの変数はその年の翌年1月1日の住民基本台帳人口。
  政令市: 元データに市全体の行があるものはそれを使い（住宅・土地統計調査・公共施設状況調）、区しかない場合（地価調査の基準地）は
          区→市の対応（国勢調査 b02_07 の並び）で市にまとめる。
住宅・土地統計調査は市・区と人口1.5万人以上の町村だけが対象のため、それ以外の町村は欠損。
"""
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
RAW = BASE / "04_data" / "01_raw"
ADD = RAW / "16_追加変数_住宅環境"
OUT = BASE / "04_data" / "02_processed"
YEARS = [2022, 2023, 2024, 2025]  # データ年（→ 年度版 2023〜2026）
FIELD = "住宅環境"

master = pd.read_csv(OUT / "01_市区町村別_個別KPI.csv", dtype={"市区町村コード": str})
master = master[["市区町村コード", "都道府県", "市区町村", "区分", "人口"]]
codes = master["市区町村コード"]
TOKYO23 = codes[codes.str.match(r"131\d\d") & (codes != "13100")]

# 政令市の区 → 市（03_追加変数の作成.py と同じ作り方）
cen = pd.read_excel(RAW / "02_国勢調査2020" / "b02_07.xlsx", header=None, skiprows=12, dtype=str, usecols=[0, 1, 2, 7])
cen = cen[(cen[0] == "0_国籍総数") & (cen[1] == "0_総数")]
ward2city, cur = {}, None
for k, c in zip(cen[2], cen[7]):
    if k == "1":
        cur = c
    elif k == "0" and cur and not c.startswith("131"):
        ward2city[c] = cur
ward2city.update({"22138": "22130", "22139": "22130", "22140": "22130"})  # 浜松市の新3区（2024年〜）


def num(s):
    """数値化。e-Stat・総務省の表の「-」は該当なし＝0、「X」「…」などは欠損。"""
    if isinstance(s, pd.Series) and s.dtype != float:
        s = s.where(s.astype(str).str.strip() != "-", "0")
    return pd.to_numeric(s, errors="coerce")


# ---------------------------------------------------------------- 記録
VALUES = {}   # 列名 -> {データ年: Series}
DEFS = {}     # 列名 -> dict


def define(col, disp, sign, unit, formula, src, year, yearly, sub, op, op_reason):
    DEFS[col] = {"列名": col, "表示名": disp, "分野": FIELD, "望ましい向き": sign, "単位": unit, "計算式": formula,
                 "出典": src, "データ年": year, "年ごとの値の有無": yearly, "代用": sub,
                 "操作可能性": op, "操作可能性の理由": op_reason}


def put(col, s, years=YEARS):
    """years のすべてに同じ値（1時点の変数）"""
    s = s[~s.index.duplicated()].reindex(codes.values)
    VALUES.setdefault(col, {}).update({y: s for y in years})


# ---------------------------------------------------------------- 住基人口（各年1月1日。データ年 y ← y+1年1月1日）
POP = {}
for y in YEARS:
    df = pd.read_excel(RAW / "06_健康寿命" / f"{(y + 1) % 100:02d}04ssnen.xlsx", header=None, skiprows=3, dtype=str)
    df = df[df[0].str.fullmatch(r"\d{6}", na=False) & (df[3] == "計")]
    df = df.set_index(df[0].str[:5])
    POP[y] = num(df[4])[~df.index.duplicated()]


# ---------------------------------------------------------------- ① 住宅・土地統計調査2023（e-Stat 全国一括Excel 共通の読み方）
def jutaku(name, ncat):
    """地域区分（1列目）の先頭5桁をコードにし、分類事項の列（2列目から ncat 列）を文字のまま残す。
    数値列は「-」を0にする。政令市・特別区部は市全体の行（地域識別コード1）がある。"""
    df = pd.read_excel(ADD / name, header=None, skiprows=9, dtype=str)
    df = df[df[1].str.match(r"\d{5}_", na=False)].copy()
    df["code"] = df[1].str[:5]
    return df


SRC_JT = "総務省統計局「令和5年住宅・土地統計調査」住宅及び世帯に関する基本集計（確報集計）"
NOTE_JT = "。市・区と人口1.5万人以上の町村のみ"
ONE = dict(year="2023/10/1", yearly="なし（1時点）", sub="全年度版に2023年の値")

# 1 高齢者等のための設備がある住宅の割合（第25-3表）
t = jutaku("e025_3.xlsx", 2)
t = t[(t[2] == "0_総数") & (t[3] == "0_総数")].drop_duplicates("code").set_index("code")
put("高齢者等設備のある住宅割合", num(t[5]) / (num(t[5]) + num(t[20])) * 100)
define("高齢者等設備のある住宅割合", "高齢者等のための設備（手すり・段差のない屋内など）がある住宅の割合", 1, "%",
       "高齢者等のための設備がある住宅数 ÷（ある ＋ ない）×100（居住世帯のある住宅、不詳を除く）。設備は手すり・またぎやすい浴槽・"
       "浴室暖房乾燥機・車いすで通行可能な廊下幅・段差のない屋内・道路から玄関まで車いすで通行可能のいずれか" + NOTE_JT,
       SRC_JT + " 第25-3表（e025_3.xlsx）", **ONE, op="動かせる",
       op_reason="住宅のバリアフリー改修の助成（介護保険の住宅改修・市独自の補助）で増やせる")

# 2 1980年以前に建築された住宅の割合（第5-3表）
t = jutaku("e005_3.xlsx", 1)
t = t.drop_duplicates(["code", 2]).pivot(index="code", columns=2, values=3).apply(num)
known = t.drop(columns="00_総数").sum(axis=1)   # 建築の時期不詳を除く
put("旧耐震住宅割合", (t["01_1970年以前"] + t["02_1971～1980年"]) / known * 100)
define("旧耐震住宅割合", "1980年以前に建築された住宅（旧耐震基準）の割合", -1, "%",
       "建築の時期が1980年以前の住宅数 ÷ 建築の時期が分かる住宅数 ×100（居住世帯のある住宅）" + NOTE_JT,
       SRC_JT + " 第5-3表（e005_3.xlsx）", **ONE, op="動かせない",
       op_reason="住宅ストックの築年は建替えでしか変わらず、市の施策で短期に動かせる幅が小さい")

# 3 2019年以降に増改築・改修工事をした持ち家の割合（第36表）
t = jutaku("e036.xlsx", 1)
t = t[t[2] == "0_総数"].drop_duplicates("code").set_index("code")
put("改修工事をした持ち家割合", num(t[4]) / num(t[3]) * 100)
define("改修工事をした持ち家割合", "2019年以降に増改築・改修工事をした持ち家の割合", 1, "%",
       "2019年以降に増改築・改修工事等（増築・間取り変更、台所・トイレ・浴室の改修、内装、屋根・外壁、補強、断熱など）をした持ち家数 ÷ 持ち家数 ×100"
       + NOTE_JT, SRC_JT + " 第36表（e036.xlsx）", **ONE, op="動かせる",
       op_reason="住宅リフォーム・耐震改修・省エネ改修の補助で増やせる")

# 4 二重サッシ・複層ガラスの窓がある住宅の割合（第30-2表）
t = jutaku("e030_2.xlsx", 3)
t = t[(t[2] == "0_総数") & (t[3] == "0_総数") & (t[4] == "00_総数")].drop_duplicates("code").set_index("code")
put("二重サッシ住宅割合", (num(t[10]) + num(t[11])) / (num(t[10]) + num(t[11]) + num(t[12])) * 100)
define("二重サッシ住宅割合", "二重以上のサッシ又は複層ガラスの窓がある住宅の割合", 1, "%",
       "二重以上のサッシ又は複層ガラスの窓が（すべての窓に ＋ 一部の窓に）ある住宅数 ÷（ある ＋ ない）×100（不詳を除く）。断熱・遮音性能の目安"
       + NOTE_JT, SRC_JT + " 第30-2表（e030_2.xlsx）", **ONE, op="動かせる",
       op_reason="窓の断熱改修（省エネ改修）の補助で増やせる")

# 5 腐朽・破損のある住宅の割合（第32-2表）
t = jutaku("e032_2.xlsx", 2)
t = t[t[3] == "00_総数"].drop_duplicates(["code", 2]).pivot(index="code", columns=2, values=4).apply(num)
put("腐朽破損住宅割合", t["1_腐朽・破損あり"] / (t["1_腐朽・破損あり"] + t["2_腐朽・破損なし"]) * 100)
define("腐朽破損住宅割合", "腐朽・破損のある住宅の割合", -1, "%",
       "腐朽・破損のある住宅数 ÷（ある ＋ ない）×100（居住世帯のある住宅）" + NOTE_JT,
       SRC_JT + " 第32-2表（e032_2.xlsx）", **ONE, op="動かせる",
       op_reason="住宅の修繕・リフォームの補助、老朽危険家屋の除却補助で減らせる")

# 6 賃貸・売却用及び二次的住宅を除く空き家の割合（第1-2表）
t = jutaku("e001_2.xlsx", 0).drop_duplicates("code").set_index("code")
put("放置空き家割合", num(t[9]) / num(t[2]) * 100)
define("放置空き家割合", "賃貸・売却用及び二次的住宅を除く空き家（いわゆる放置空き家）の割合", -1, "%",
       "賃貸・売却用及び二次的住宅を除く空き家数 ÷ 総住宅数 ×100。空き家全体ではなく、市の空き家対策の対象となる長期不在・取壊し予定などの空き家"
       + NOTE_JT, SRC_JT + " 第1-2表（e001_2.xlsx）", **ONE, op="動かせる",
       op_reason="空家等対策計画に基づく除却・利活用（空き家バンク等）で減らせる")

# 7 民営借家の延べ面積1m²当たり家賃（第122-4表）
t = jutaku("e122_4.xlsx", 1)
t = t[t[2] == "3_民営借家"].drop_duplicates("code").set_index("code")
put("民営借家の1m2当たり家賃", num(t[16]))
define("民営借家の1m2当たり家賃", "民営借家（専用住宅）の延べ面積1m²当たり家賃", -1, "円/m²",
       "民営借家（専用住宅）の延べ面積1m²当たり1か月の家賃（家賃0円を含まない）" + NOTE_JT,
       SRC_JT + " 第122-4表（e122_4.xlsx）", **ONE, op="動かせない",
       op_reason="家賃水準は市場で決まり、市の施策ではほとんど動かせない")

# ---------------------------------------------------------------- ② 地価調査（国土数値情報 L02）住宅地の平均価格（年ごと）
VALUES["住宅地の平均地価"] = {}
for y in YEARS:
    with zipfile.ZipFile(ADD / f"L02-{y % 100}_GML.zip") as z:
        g = json.loads(z.read(f"L02-{y % 100}.geojson"))
    pts = pd.DataFrame([f["properties"] for f in g["features"]])
    pts = pts[pts["L02_001"] == "000"]                   # 用途区分 000＝住宅地
    city = pts["L02_020"].map(lambda c: ward2city.get(c, c))   # 政令市の区の基準地は市にまとめる
    s = pd.to_numeric(pts["L02_006"]).groupby(city).mean()
    VALUES["住宅地の平均地価"][y] = s.reindex(codes.values)
define("住宅地の平均地価", "住宅地の平均価格（都道府県地価調査）", -1, "円/m²",
       "都道府県地価調査の基準地のうち用途が住宅地の地点の価格（各年7月1日時点）を市区町村ごとに単純平均（政令市は全区の地点を平均）。"
       "住宅地の基準地がない市区町村は欠損",
       "国土交通省「国土数値情報 地価調査データ（L02）」2022〜2025年（L02-YY_GML.zip）", "2022〜2025（各年7月1日）", "あり", "なし",
       op="動かせない", op_reason="地価は市場で決まり、市の施策ではほとんど動かせない")

# ---------------------------------------------------------------- 公共施設状況調（手元の原本、年度ごと、3月31日現在）
pk = pd.read_excel(RAW / "12_公共施設状況調" / "市町村経年比較表_H18-R06_001068878.xlsx", sheet_name="AFAHO14H1030",
                   header=None, dtype=str)
hdr = pk.iloc[:7].fillna("").agg(lambda c: "/".join(map(str, c)).replace("\n", ""))
pk = pk.iloc[7:]
pk = pk[pk[2].str.fullmatch(r"\d{6}", na=False)]
pk_years = sorted(int(v) for v in pk[0].str.strip().unique() if str(v).isdigit())


def pk_cols(start, *keys):
    """見出しにキーをすべて含む列（start 列以降）"""
    return [j for j, h in hdr.items() if j >= start and all(k in h for k in keys)]


HOUSING = [pk_cols(0, "公営住宅(戸)", "計")[0], pk_cols(0, "改良住宅(戸)", "計")[0], pk_cols(0, "単独住宅(戸)", "計")[0]]
SEWER0 = pk_cols(0, "八　下水道等", "1　公共下水道")[0]
SEWER = pk_cols(SEWER0, "現在処理区域内人口")[0]   # 公共下水道の現在処理区域内人口（八 下水道等の最初の「現在処理区域内人口」）
assert SEWER < pk_cols(0, "2　都市下水路")[0], hdr[SEWER]

VALUES["人口あたり公営住宅戸数"], VALUES["下水道処理人口普及率"] = {}, {}
for y in YEARS:
    fy = min(y, max(pk_years))
    d = pk[pk[0].str.strip() == str(fy)]
    d = d.set_index(d[2].str[:5])
    d = d[~d.index.duplicated()]
    house = sum(num(d[c]).fillna(0) for c in HOUSING)
    sewer = num(d[SEWER]).fillna(0)
    # 東京23区の下水道は東京都が一括経営し、千代田区の行に23区分がまとめて計上されているため、23区全体の普及率を各区に付ける
    rate = sewer / POP[fy] * 100
    rate[TOKYO23] = sewer.reindex(TOKYO23).sum() / POP[fy].reindex(TOKYO23).sum() * 100
    VALUES["人口あたり公営住宅戸数"][y] = (house / POP[fy] * 1e4).reindex(codes.values)   # 代用年は値ごと（分母も）その年度のもの
    VALUES["下水道処理人口普及率"][y] = rate.reindex(codes.values)
SRC_PK = "総務省「公共施設状況調経年比較表」市町村経年比較表（12_公共施設状況調）"
define("人口あたり公営住宅戸数", "人口1万人あたり市町村営の公営住宅等の戸数", 1, "戸/1万人",
       "市町村営の公営住宅＋改良住宅＋単独住宅の戸数（3月31日現在、「-」は0。都道府県営は含まない）÷ 住基人口（その年度末に近い翌年1月1日）×1万",
       SRC_PK, "2022〜2024年度", "あり", "2026年度版（2025年度）は未公表のため2024年度の値で代用",
       op="動かせる", op_reason="市営住宅の供給・建替え・用途廃止は市が決める")
define("下水道処理人口普及率", "下水道処理人口普及率（公共下水道）", 1, "%",
       "公共下水道の現在処理区域内人口（3月31日現在、「-」は0）÷ 住基人口（その年度末に近い翌年1月1日）×100（100%を少し超える市町村あり）。"
       "集落排水・合併浄化槽などを含む「汚水処理人口普及率」は、公共施設状況調の浄化槽の処理人口に計上漏れとみられる値があり、"
       "国の市町村別一覧は画像のPDFで読み取れないため使わない。東京23区は下水道の値が千代田区の行に23区分まとめて計上されているため、"
       "23区全体の値を各区に付けた",
       SRC_PK, "2022〜2024年度", "あり", "2026年度版（2025年度）は未公表のため2024年度の値で代用",
       op="動かせる", op_reason="公共下水道の整備（処理区域の拡大）は市町村の事業")

# ---------------------------------------------------------------- 出力
cols = list(VALUES)
rows = []
for y in YEARS:
    d = pd.DataFrame({c: VALUES[c][y].values for c in cols}, index=codes.values)
    d.insert(0, "年度版", y + 1)
    rows.append(d)
panel = pd.concat(rows).rename_axis("市区町村コード").reset_index()
panel[cols] = panel[cols].replace([np.inf, -np.inf], np.nan)   # 人口0（双葉町）など分母0の割り算
panel = panel.sort_values(["市区町村コード", "年度版"])
OUT.mkdir(parents=True, exist_ok=True)
panel.round(4).to_csv(OUT / "05_追加変数_住宅環境.csv", index=False, encoding="utf-8-sig")
defs = pd.DataFrame([DEFS[c] for c in cols])
defs.to_csv(OUT / "05_追加変数_住宅環境_定義.csv", index=False, encoding="utf-8-sig")

print(panel.shape)
miss = panel.groupby("年度版")[cols].apply(lambda d: d.isna().sum()).T
print("欠損件数（年度版別, 全1,741）"); print(miss.to_string())
print(panel[cols].describe().T.round(2).to_string())
w = panel[panel["市区町村コード"] == "30201"].set_index(["市区町村コード", "年度版"])
print(w.round(3).T.to_string())
