"""「地域とのつながり」「自己効力感」の説明候補となる追加変数を、市区町村 × 年度版の表にまとめる。

入力 : 04_data/01_raw/14_追加変数/（05_scripts/01_download/14_追加変数.py で取得）
       手元の原本 02_国勢調査2020/c01_02.xlsx, 06_健康寿命/YYMMssnen.xlsx, 08_住民基本台帳人口移動報告/b01103s_*,
       09_経済センサス2021/b1_009_1a.xlsx, 12_公共施設状況調/市町村経年比較表
       行の土台：04_data/02_processed/01_市区町村別_個別KPI.csv（1,741市区町村）
出力 : 04_data/02_processed/03_追加変数.csv（市区町村コード, 年度版, 各変数）
       04_data/02_processed/03_追加変数_定義.csv

行   : 全国の市区町村（政令市は市全体の1行、東京23区は区ごと）＝1,741 × 年度版4（2023〜2026）
年度版: 02_個別KPIの年度パネル作成.py と同じく「年度版Y ← Y−1年（暦年・年度）の値」。
        未公表の年は最も近い前の年で代用し、定義CSVの「代用」に記録する。1時点の変数は全年度版に同じ値。
        人口あたりの分母は、年ごとの変数はその年の翌年1月1日の住民基本台帳人口、1時点の変数は国勢調査2020の人口。
政令市: 元データに市全体の行があるものはそれを使い、区しかない場合は区の合計で市の値を作る
        （区→市の対応は 02_個別KPIの年度パネル作成.py と同じく国勢調査 b02_07 の並びから作る）。
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf

BASE = Path(__file__).resolve().parents[2]
RAW = BASE / "04_data" / "01_raw"
ADD = RAW / "14_追加変数"
OUT = BASE / "04_data" / "02_processed"
YEARS = [2022, 2023, 2024, 2025]  # データ年（→ 年度版 2023〜2026）

master = pd.read_csv(OUT / "01_市区町村別_個別KPI.csv", dtype={"市区町村コード": str})
master = master[["市区町村コード", "都道府県", "市区町村", "区分", "人口"]]
codes = master["市区町村コード"]
POP2020 = master.set_index("市区町村コード")["人口"]
PREFS = list(dict.fromkeys(master["都道府県"]))
name2code = {(p, n.replace("ヶ", "ケ")): c for c, p, n in zip(master["市区町村コード"], master["都道府県"], master["市区町村"])}

# 政令市の区 → 市（02_個別KPIの年度パネル作成.py と同じ作り方）
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


def fill_city(s):
    """件数系の値：市全体の行がない政令市は区の合計で埋める。"""
    s = s[~s.index.duplicated()]
    w = s[s.index.isin(ward2city)]
    city = w.groupby(w.index.map(ward2city)).sum(min_count=1)
    return s.combine_first(city)


# ---------------------------------------------------------------- 記録
VALUES = {}   # 列名 -> {データ年: Series}
DEFS = {}     # 列名 -> dict


def define(col, disp, field, sign, unit, formula, src, year, yearly, sub):
    DEFS[col] = {"列名": col, "表示名": disp, "分野": field, "望ましい向き": sign, "単位": unit, "計算式": formula,
                 "出典": src, "データ年": year, "年ごとの値の有無": yearly, "代用": sub}


def put(col, s, years=YEARS):
    """years のすべてに同じ値（1時点の変数）"""
    s = s[~s.index.duplicated()].reindex(codes.values)
    VALUES.setdefault(col, {}).update({y: s for y in years})


# ---------------------------------------------------------------- 住基人口（各年1月1日。データ年 y ← y+1年1月1日）
POP, POP2039, POP65 = {}, {}, {}
for y in YEARS:
    df = pd.read_excel(RAW / "06_健康寿命" / f"{(y + 1) % 100:02d}04ssnen.xlsx", header=None, skiprows=3, dtype=str)
    df = df[df[0].str.fullmatch(r"\d{6}", na=False) & (df[3] == "計")]
    df = df.set_index(df[0].str[:5])
    df = df[~df.index.duplicated()]
    POP[y] = num(df[4])
    POP2039[y] = df.iloc[:, 9:13].apply(num).sum(axis=1)   # 20〜24, 25〜29, 30〜34, 35〜39歳
    POP65[y] = df.iloc[:, 18:26].apply(num).sum(axis=1)    # 65歳以上
SRC_JUKI = "総務省「住民基本台帳に基づく人口、人口動態及び世帯数調査」（06_健康寿命/YYMMssnen.xlsx）"


# ---------------------------------------------------------------- 国勢調査2020（e-Stat 全国一括Excel 共通の読み方）
def census(path, skip, name_col):
    """地域名列の先頭5桁をコードにする。旧市区町村（「旧：」）の行は除く。"""
    df = pd.read_excel(path, header=None, skiprows=skip, dtype=str)
    df = df[df[name_col].notna() & ~df[name_col].astype(str).str.contains("旧：")]
    df["code"] = df[name_col].str[:5]
    return df


SRC_CENSUS = "総務省統計局「令和2年国勢調査」"

# 1 居住期間20年以上の人口割合
f8 = census(ADD / "f08_01.xlsx", 10, 4)
f8 = f8[f8[0] == "0_総数"].pivot_table(index="code", columns=1, values=5, aggfunc="first").apply(num)
known = f8["0_総数"] - f8["7_居住期間「不詳」"].fillna(0)
put("居住期間20年以上割合", (f8["1_出生時から"] + f8["6_20年以上"]) / known * 100)
define("居住期間20年以上割合", "居住期間20年以上（出生時からを含む）の人口割合", "地域とのつながり", 1, "%",
       "（出生時から ＋ 20年以上）÷（総数 − 居住期間不詳）×100。居住期間は「現在の場所（住所）」に住んでいる期間",
       SRC_CENSUS + " 移動人口 第8-1表（f08_01.xlsx）", "2020", "なし（1時点）", "全年度版に2020年の値")

# 6 共同住宅に住む一般世帯の割合
b19 = census(ADD / "b19_04.xlsx", 10, 2)
b19 = b19[b19[3] == "0_総数"].drop_duplicates("code").set_index("code")
put("共同住宅世帯割合", num(b19[8]) / num(b19[4]) * 100)
define("共同住宅世帯割合", "共同住宅に住む一般世帯の割合", "地域とのつながり", -1, "%",
       "共同住宅に住む一般世帯数 ÷ 一般世帯総数 ×100", SRC_CENSUS + " 人口等基本集計 第19-4表（b19_04.xlsx）",
       "2020", "なし（1時点）", "全年度版に2020年の値")

# 8 就業率・女性就業率・65歳以上就業率（手元 c01_02）
lab = census(RAW / "02_国勢調査2020" / "c01_02.xlsx", 10, 2)
lab = lab.set_index(["code", 3, 4])
lab = lab[~lab.index.duplicated()]


def emp_rate(sex, age):
    t = lab.xs((sex, age), level=[1, 2])
    return num(t[7]) / (num(t[5]) - num(t[17]).fillna(0)) * 100


put("就業率", emp_rate("0_総数", "00_総数"))
put("女性就業率", emp_rate("2_女", "00_総数"))
put("65歳以上就業率", emp_rate("0_総数", "R2_（再掲）65歳以上"))
for col, disp, who in [("就業率", "就業率（15歳以上）", "15歳以上人口"), ("女性就業率", "女性の就業率（15歳以上）", "15歳以上女性人口"),
                       ("65歳以上就業率", "65歳以上の就業率", "65歳以上人口")]:
    define(col, disp, "自己効力感", 1, "%", f"就業者 ÷（{who} − 労働力状態不詳）×100",
           SRC_CENSUS + " 就業状態等基本集計 第1-2表（02_国勢調査2020/c01_02.xlsx）", "2020", "なし（1時点）", "全年度版に2020年の値")

# 8 正規の職員・従業員の割合
c3 = census(ADD / "c03_02.xlsx", 10, 2)
c3 = c3[c3[3] == "0_総数"].drop_duplicates("code").set_index("code")
put("正規雇用割合", num(c3[6]) / num(c3[5]) * 100)
define("正規雇用割合", "雇用者に占める正規の職員・従業員の割合", "自己効力感", 1, "%",
       "正規の職員・従業員 ÷ 雇用者（役員を除く）×100", SRC_CENSUS + " 就業状態等基本集計 第3-2表（c03_02.xlsx）",
       "2020", "なし（1時点）", "全年度版に2020年の値")

# 9 大学・大学院卒業者の割合
c11 = census(ADD / "c11_02.xlsx", 10, 2)
c11 = c11[(c11[3] == "0_総数") & (c11[4] == "00_総数")].drop_duplicates("code").set_index("code")
grad = num(c11[6]) - num(c11[13]).fillna(0)
put("大学卒業者割合", (num(c11[11]) + num(c11[12]).fillna(0)) / grad * 100)
define("大学卒業者割合", "卒業者に占める大学・大学院卒業者の割合", "自己効力感", 1, "%",
       "（最終卒業学校が大学 ＋ 大学院）÷（卒業者 − 最終卒業学校不詳）×100（15歳以上）",
       SRC_CENSUS + " 就業状態等基本集計 第11-2表（c11_02.xlsx）", "2020", "なし（1時点）", "全年度版に2020年の値")


# ---------------------------------------------------------------- 統計でみる市区町村のすがた
def sugata(path, colmap):
    df = pd.read_excel(path, header=None, skiprows=10, dtype=str)
    df["code"] = df.iloc[:, -1].str.strip()
    df = df[df["code"].str.fullmatch(r"\d{5}", na=False)].set_index("code")
    df = df[~df.index.duplicated()]
    return pd.DataFrame({name: num(df.iloc[:, i]) for i, name in colmap.items()})


SRC_SUGATA = "総務省統計局「統計でみる市区町村のすがた」"

# 6 昼夜間人口比率・他市区町村への通勤者の割合
a = sugata(ADD / "2026-a.xls", {10: "総人口", 22: "昼間人口"})
f = sugata(ADD / "2026-f.xls", {11: "就業者", 22: "他市区町村へ通勤"})
put("昼夜間人口比率", a["昼間人口"] / a["総人口"] * 100)
put("他市区町村への通勤者割合", f["他市区町村へ通勤"] / f["就業者"] * 100)
define("昼夜間人口比率", "昼夜間人口比率", "地域とのつながり", 1, "%", "昼間人口（A6107）÷ 総人口（A1101）×100",
       SRC_SUGATA + "2026 A 人口・世帯（2026-a.xls。元は国勢調査2020）", "2020", "なし（1時点）", "全年度版に2020年の値")
define("他市区町村への通勤者割合", "就業者に占める他市区町村への通勤者の割合", "地域とのつながり", -1, "%",
       "他市区町村への通勤者数（F2705）÷ 就業者数（F1102）×100（通学者は含まない）",
       SRC_SUGATA + "2026 F 労働（2026-f.xls。元は国勢調査2020）", "2020", "なし（1時点）", "全年度版に2020年の値")

# 7 納税義務者1人あたり課税対象所得（すがた C、年ごと）
inc = {}
for edition, y in [("2024", 2022), ("2025", 2023), ("2026", 2024)]:
    c = sugata(ADD / f"{edition}-c.xls", {10: "所得", 11: "納税義務者"})
    inc[y] = c["所得"] / c["納税義務者"] * 1000   # 百万円/人 → 千円/人
inc[2025] = inc[2024]
VALUES["納税義務者1人あたり課税対象所得"] = {y: inc[y].reindex(codes.values) for y in YEARS}
define("納税義務者1人あたり課税対象所得", "納税義務者1人あたり課税対象所得", "自己効力感", 1, "千円/人",
       "課税対象所得（C120110）÷ 納税義務者数（所得割）（C120120）",
       SRC_SUGATA + "2024・2025・2026 C 経済基盤（YYYY-c.xls。元は総務省「市町村税課税状況等の調」）",
       "2022・2023・2024（すがたの年次表記）", "あり", "2026年度版（2025年）は未公表のため2024年の値で代用")

# ---------------------------------------------------------------- 10・11 20〜39歳人口割合・転入超過率（住基、年ごと）
mig = {}
for y in YEARS:
    f_ = next((RAW / "08_住民基本台帳人口移動報告").glob(f"b01103s_*_{y}.xlsx"))
    df = pd.read_excel(f_, header=None, skiprows=6, dtype=str)
    df = df[df[2] == "移動者"]
    s = df.set_index(df[5].str.zfill(5)).iloc[:, 12:16].apply(num).sum(axis=1)   # 20〜24, 25〜29, 30〜34, 35〜39歳
    mig[y] = s[~s.index.duplicated()]
VALUES["20_39歳人口割合"] = {y: (POP2039[y] / POP[y] * 100).reindex(codes.values) for y in YEARS}
VALUES["20_39歳転入超過率"] = {y: (fill_city(mig[y]) / POP2039[y] * 100).reindex(codes.values) for y in YEARS}
define("20_39歳人口割合", "20〜39歳人口の割合", "自己効力感", 1, "%", "20〜39歳人口 ÷ 総人口 ×100（データ年の翌年1月1日の住基人口）",
       SRC_JUKI, "2023/1/1〜2026/1/1（データ年2022〜2025）", "あり", "なし")
define("20_39歳転入超過率", "20〜39歳の転入超過率", "自己効力感", 1, "%",
       "20〜39歳の転入超過数（国内移動、日本人・外国人計）÷ 20〜39歳人口（翌年1月1日の住基人口）×100",
       "総務省統計局「住民基本台帳人口移動報告」年報 表11-3（08_住民基本台帳人口移動報告/b01103s）", "2022〜2025", "あり", "なし")

# ---------------------------------------------------------------- 2 人口あたり政治・経済・文化団体の事業所数（経済センサス2021）
raw = pd.read_excel(RAW / "09_経済センサス2021" / "b1_009_1a.xlsx", header=None, dtype=str)
col = raw.columns[raw.iloc[5] == "93_政治・経済・文化団体"][0]
df = raw.iloc[9:]
s = fill_city(num(df.set_index(df[1].str[:5])[col]))
put("人口あたり政治経済文化団体の事業所数", s.reindex(codes.values) / POP2020 * 1e5)
define("人口あたり政治経済文化団体の事業所数", "人口10万人あたり政治・経済・文化団体の事業所数", "地域とのつながり", 1, "所/10万人",
       "産業中分類「93_政治・経済・文化団体」（経済団体・労働団体・学術文化団体・政治団体・他に分類されない非営利的団体）の全事業所数 ÷ 人口（国勢調査2020）×10万",
       "令和3年経済センサス‐活動調査 第9-1A表（09_経済センサス2021/b1_009_1a.xlsx）", "2021/6/1", "なし（1時点）", "全年度版に2021年の値")

# 13 新設事業所（経済センサス2021 第30表）
ec = pd.read_excel(ADD / "b1_030.xlsx", header=None, skiprows=9, dtype=str)
ec = ec[ec[1].notna()]
ec = ec.set_index(ec[1].str[:5])
ec = ec[~ec.index.duplicated()]
new = fill_city(num(ec[8]))
tot = fill_city(num(ec[6]))
put("人口あたり新設事業所数", new.reindex(codes.values) / POP2020 * 1000)
put("新設事業所割合", (new / tot * 100).reindex(codes.values))
define("人口あたり新設事業所数", "人口千人あたり新設事業所数（2016〜2021年）", "自己効力感", 1, "所/千人",
       "新設事業所数（2016年経済センサス‐活動調査以降に新設、民営、事業内容等不詳を除く）÷ 人口（国勢調査2020）×1000",
       "令和3年経済センサス‐活動調査 第30表（b1_030.xlsx）", "2016/6〜2021/6", "なし（1時点）", "全年度版に2021年の値")
define("新設事業所割合", "民営事業所に占める新設事業所の割合", "自己効力感", 1, "%",
       "新設事業所数 ÷ 民営事業所数（存続＋新設、事業内容等不詳を除く）×100",
       "令和3年経済センサス‐活動調査 第30表（b1_030.xlsx）", "2016/6〜2021/6", "なし（1時点）", "全年度版に2021年の値")

# ---------------------------------------------------------------- 4 公民館・図書館・社会体育施設・集会施設（公共施設状況調、年度ごと、市町村立）
pk = pd.read_excel(RAW / "12_公共施設状況調" / "市町村経年比較表_H18-R06_001068878.xlsx", sheet_name="AFAHO14H1030",
                   header=None, dtype=str)
hdr = pk.iloc[:7].fillna("").agg(lambda c: "/".join(map(str, c)))
pk = pk.iloc[7:]
pk = pk[pk[2].str.fullmatch(r"\d{6}", na=False)]
pk_years = sorted(int(v) for v in pk[0].str.strip().unique() if str(v).isdigit())


def pk_col(*keys):
    return next(j for j, h in hdr.items() if all(k in h for k in keys))


FAC = {"公民館": [pk_col("公民館", "箇所数")], "図書館": [pk_col("図書館", "箇所数")],
       "社会体育施設": [pk_col("体育館", "箇所数"), pk_col("陸上競技場", "箇所数"), pk_col("野球場", "箇所数"), pk_col("プール", "箇所数")],
       "集会施設": [pk_col("集会施設", "合計", "箇所数")]}
for name, cols in FAC.items():
    col = f"人口あたり{name}数"
    VALUES[col] = {}
    for y in YEARS:
        fy = min(y, max(pk_years))
        d = pk[pk[0].str.strip() == str(fy)]
        cnt = sum(num(d[c].replace("-", "0")).fillna(0) for c in cols)
        s = pd.Series(cnt.values, index=d[2].str[:5].values)
        s = s[~s.index.duplicated()]
        VALUES[col][y] = (s / POP[fy] * 1e5).reindex(codes.values)   # 代用年は値ごと（分母も）その年度のもの
detail = {"公民館": "公民館の箇所数", "図書館": "図書館の箇所数",
          "社会体育施設": "体育施設（体育館＋陸上競技場＋野球場＋プール）の箇所数",
          "集会施設": "「十四 その他施設 3 市町村立施設 集会施設 合計」の箇所数（自治会館・集会所等。区分の詳細は調査の記入要領による）"}
for name in FAC:
    define(f"人口あたり{name}数", f"人口10万人あたり{name}数（市町村立）", "地域とのつながり", 1, "施設/10万人",
           f"市町村立の{detail[name]}（3月31日現在、「-」は0）÷ 住基人口（その年度末に近い翌年1月1日）×10万",
           "総務省「公共施設状況調経年比較表」市町村経年比較表（12_公共施設状況調）", "2022〜2024年度", "あり",
           "2026年度版（2025年度）は未公表のため2024年度の値で代用")

# ---------------------------------------------------------------- 3 介護予防の通いの場（厚労省 総合事業調査、年度ごと）
kayoi = {}
unmatched_kayoi = set()
for y, f_ in [(2022, "通いの場_R04.xlsx"), (2023, "通いの場_R05.xlsx"), (2024, "通いの場_R06.xlsx")]:
    df = pd.read_excel(ADD / f_, header=None, dtype=str)
    assert "箇所数" in str(df.iloc[:9, 7].tolist()) and "参加者実人数" in str(df.iloc[:9, 19].tolist())
    df = df.iloc[10:]
    df = df[df[0].notna() & df[1].notna()]
    keys = list(zip(df[3], df[1].str.replace("ヶ", "ケ")))
    unmatched_kayoi |= {k for k in keys if k not in name2code}
    idx = [name2code.get(k) for k in keys]
    kayoi[y] = pd.DataFrame({"箇所": num(df[7]).values, "参加者": num(df[19]).values}, index=idx)
    kayoi[y] = kayoi[y][kayoi[y].index.notna()]
if unmatched_kayoi:
    print("  通いの場：照合できなかった市町村", sorted(unmatched_kayoi))
VALUES["高齢者千人あたり通いの場の箇所数"], VALUES["通いの場の参加率"] = {}, {}
for y in YEARS:
    sy = min(y, 2024)
    VALUES["高齢者千人あたり通いの場の箇所数"][y] = (kayoi[sy]["箇所"] / POP65[sy] * 1000).reindex(codes.values)
    VALUES["通いの場の参加率"][y] = (kayoi[sy]["参加者"] / POP65[sy] * 100).reindex(codes.values)
SRC_KAYOI = "厚生労働省「介護予防・日常生活支援総合事業（地域支援事業）の実施状況に関する調査」通いの場の展開状況 市町村別（通いの場_R0N.xlsx）"
define("高齢者千人あたり通いの場の箇所数", "65歳以上人口千人あたり 介護予防の通いの場の箇所数", "地域とのつながり", 1, "箇所/65歳以上千人",
       "住民主体の通いの場の箇所数（計）÷ 65歳以上住基人口（年度末に近い翌年1月1日）×1000", SRC_KAYOI, "2022〜2024年度", "あり",
       "2026年度版（2025年度）は未公表のため2024年度の値で代用")
define("通いの場の参加率", "介護予防の通いの場への参加率（65歳以上人口比）", "地域とのつながり", 1, "%",
       "通いの場の参加者実人数（計。65歳未満の参加者も含みうる）÷ 65歳以上住基人口（翌年1月1日）×100", SRC_KAYOI, "2022〜2024年度", "あり",
       "2026年度版（2025年度）は未公表のため2024年度の値で代用")


# ---------------------------------------------------------------- 5 地域おこし協力隊（総務省 報道資料PDFの「活躍先」一覧、年度ごと）
def kyoryokutai(path):
    """PDFの一覧（都道府県名・市町村名・隊員数の多段組）から市町村名と隊員数を読み取る。
    市町村名の右隣にある数値を隊員数とし、同名の市町村（森町・美郷町など）は一覧の並び（都道府県順・コード順）で判定する。
    「★」付きは都道府県の受入れのため除く。"""
    NUM = re.compile(r"[\d,]+")
    found = []
    for pi, p in enumerate(pymupdf.open(path)):
        if "活躍先" not in p.get_text():
            continue
        ws = []
        for w in p.get_text("words"):
            if re.search(r"隊員数|受入自治体数|^[（(][\d,]+[)）]$", w[4]):
                continue
            r = pymupdf.Rect(w[:4]) * p.rotation_matrix   # 横向きのページ（R4・R5）を正立させた座標
            ws.append([r.x0, (r.y0 + r.y1) / 2, r.x1, w[4]])
        nums = [w for w in ws if NUM.fullmatch(w[3])]
        merged = []   # 1語に分かれた名前（例：「寿都」「町」）をつなぐ
        for w in sorted((w for w in ws if not NUM.fullmatch(w[3])), key=lambda w: (round(w[1]), w[0])):
            if merged and abs(merged[-1][1] - w[1]) < 2.5 and 0 <= w[0] - merged[-1][2] < 4:
                merged[-1][2] = w[2]
                merged[-1][3] += w[3]
            else:
                merged.append(list(w))
        cand = sorted((abs(n[1] - t[1]), n[0] - t[2], i, j) for i, t in enumerate(merged) for j, n in enumerate(nums)
                      if 0 <= n[0] - t[2] < 60 and abs(n[1] - t[1]) < 6)
        used_t, used_n = set(), set()
        for _, _, i, j in cand:
            if i in used_t or j in used_n:
                continue
            used_t.add(i)
            used_n.add(j)
            name = merged[i][3].replace("梼原町", "檮原町").replace("鯵ヶ沢町", "鰺ヶ沢町")
            if "★" not in name:
                found.append((pi, merged[i][0], merged[i][1], name, int(nums[j][3].replace(",", ""))))
    byname = {}
    for c, p, n in zip(master["市区町村コード"], master["都道府県"], master["市区町村"]):
        byname.setdefault(n, []).append((PREFS.index(p), c))
    rows = []   # 読む順：ページ → 段（x座標の塊）→ 上から
    for pi in sorted({a[0] for a in found}):
        pp = [a for a in found if a[0] == pi]
        cols = []
        for x in sorted({round(a[1]) for a in pp}):
            if cols and x - cols[-1][-1] < 25:
                cols[-1].append(x)
            else:
                cols.append([x])
        ci = {x: i for i, c in enumerate(cols) for x in c}
        rows += sorted(pp, key=lambda a: (ci[round(a[1])], a[2]))
    cur_p, last, res, unk = 0, "", {}, []
    for _, _, _, name, n in rows:
        cands = sorted(byname.get(name, []))
        if not cands:
            unk.append(name)
            continue
        ok = cands if len(cands) == 1 else [c for c in cands if c[0] > cur_p or (c[0] == cur_p and c[1] > last)]
        if not ok:
            ok = [c for c in cands if c[0] == cur_p] or [c for c in cands if c[0] >= cur_p]
        cur_p, last = ok[0]
        res[last] = res.get(last, 0) + n
    return pd.Series(res, dtype=float), unk


VALUES["人口あたり地域おこし協力隊員数"] = {}
for y, f_ in [(2022, "協力隊_R04.pdf"), (2023, "協力隊_R05.pdf"), (2024, "協力隊_R06.pdf"), (2025, "協力隊_R07.pdf")]:
    s, unk = kyoryokutai(ADD / f_)
    print(f"  協力隊 {y}年度：{len(s)}市町村 {int(s.sum()):,}人（都道府県受入を除く）, 照合できなかった語 {unk}")
    s = s.reindex(codes.values).fillna(0)   # 一覧に載っていない市町村は0人
    VALUES["人口あたり地域おこし協力隊員数"][y] = s / POP[y].reindex(codes.values) * 1e4
define("人口あたり地域おこし協力隊員数", "人口1万人あたり地域おこし協力隊員数", "地域とのつながり", 1, "人/1万人",
       "市町村が受け入れた隊員数（特別交付税ベース。一覧に載らない市町村は0人。都道府県の受入れは除く）÷ 住基人口（翌年1月1日）×1万。"
       "PDFの一覧から読み取り、全国の隊員数合計（都道府県分を含む）が公表値と一致することを確認",
       "総務省「地域おこし協力隊の隊員数等について」令和4〜7年度（協力隊_R0N.pdf）", "2022〜2025年度", "あり", "なし")

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
panel.round(4).to_csv(OUT / "03_追加変数.csv", index=False, encoding="utf-8-sig")
defs = pd.DataFrame([DEFS[c] for c in cols])
defs.to_csv(OUT / "03_追加変数_定義.csv", index=False, encoding="utf-8-sig")

print(panel.shape)
miss = panel.groupby("年度版")[cols].apply(lambda d: d.isna().sum()).T
print("欠損件数（年度版別, 全1,741）"); print(miss.to_string())
w = panel[panel["市区町村コード"].isin(["30201", "30206"])].set_index(["市区町村コード", "年度版"])
print(w.round(2).T.to_string())
