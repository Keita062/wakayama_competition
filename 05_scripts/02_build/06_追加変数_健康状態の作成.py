"""「健康状態」（主観）の説明候補となる追加変数を、市区町村 × 年度版の表にまとめる。

設問（主観）: 「私は、身体的に健康な状態である」「私は、精神的に健康な状態である」
             （00_context/guidebook_sources_municipalities.xlsx「健康状態」シート）

入力 : 04_data/01_raw/17_追加変数_健康状態/（05_scripts/01_download/17_追加変数_健康状態.py で取得）
       手元の原本 06_健康寿命/YYMMssnen.xlsx（住基人口）, 06_健康寿命/YY06-h2-2.xlsx（介護保険 男の認定者数）
       行の土台：04_data/02_processed/01_市区町村別_個別KPI.csv（1,741市区町村）
出力 : 04_data/02_processed/06_追加変数_健康状態.csv（市区町村コード, 年度版, 各変数）
       04_data/02_processed/06_追加変数_健康状態_定義.csv

行   : 全国の市区町村（政令市は市全体の1行、東京23区は区ごと）＝1,741 × 年度版4（2023〜2026）
年度版: 03_追加変数の作成.py と同じく「年度版Y ← Y−1年（暦年・年度）の値」。
        未公表の年は最も近い前の年で代用し、定義CSVの「代用」に記録する。1時点の変数は全年度版に同じ値。
        人口あたりの分母は、年ごとの変数はその年の翌年1月1日の住民基本台帳人口。
政令市: どの元データにも市全体の行があるため、それを使う（区の行は使わない）。
定義CSV: 03_追加変数_定義.csv の列に「操作可能性」「操作可能性の理由」を加える。
"""
import io
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
RAW = BASE / "04_data" / "01_raw"
ADD = RAW / "17_追加変数_健康状態"
OUT = BASE / "04_data" / "02_processed"
YEARS = [2022, 2023, 2024, 2025]  # データ年（→ 年度版 2023〜2026）
FIELD = "健康状態"

master = pd.read_csv(OUT / "01_市区町村別_個別KPI.csv", dtype={"市区町村コード": str})
master = master[["市区町村コード", "都道府県", "市区町村", "区分", "人口"]]
codes = master["市区町村コード"]
PREFS = list(dict.fromkeys(master["都道府県"]))
name2code = {(p, n.replace("ヶ", "ケ")): c for c, p, n in zip(master["市区町村コード"], master["都道府県"], master["市区町村"])}


def num(s):
    """数値化。e-Stat・厚労省の表の「-」は該当なし＝0、「…」「X」などは欠損。"""
    if isinstance(s, pd.Series) and s.dtype != float:
        s = s.where(s.astype(str).str.strip() != "-", "0")
    return pd.to_numeric(s, errors="coerce")


# ---------------------------------------------------------------- 記録
VALUES = {}   # 列名 -> {データ年: Series}
DEFS = {}     # 列名 -> dict


def define(col, disp, sign, unit, formula, src, year, yearly, sub, ctrl, reason):
    DEFS[col] = {"列名": col, "表示名": disp, "分野": FIELD, "望ましい向き": sign, "単位": unit, "計算式": formula,
                 "出典": src, "データ年": year, "年ごとの値の有無": yearly, "代用": sub,
                 "操作可能性": ctrl, "操作可能性の理由": reason}


def put_years(col, by_year):
    """by_year = {データ年: Series(index=市区町村コード)}。ない年は最も近い前の年で代用する。"""
    VALUES[col] = {}
    for y in YEARS:
        sy = max(k for k in by_year if k <= y)
        s = by_year[sy]
        VALUES[col][y] = s[~s.index.duplicated()].reindex(codes.values)


def sub_note(avail):
    miss = [y for y in YEARS if y not in avail]
    if not miss:
        return "なし"
    last = max(avail)
    vers = "・".join(f"{y + 1}" for y in miss)
    return f"{vers}年度版（{'・'.join(map(str, miss))}年度）は未公表のため{last}年度の値で代用"


# ---------------------------------------------------------------- 住基人口（各年1月1日。データ年 y ← y+1年1月1日）
POP, POP40, POPM6574 = {}, {}, {}
for y in YEARS:
    df = pd.read_excel(RAW / "06_健康寿命" / f"{(y + 1) % 100:02d}04ssnen.xlsx", header=None, skiprows=3, dtype=str)
    df = df[df[0].str.fullmatch(r"\d{6}", na=False)]
    df = df.set_index(df[0].str[:5])
    t = df[df[3] == "計"]
    t = t[~t.index.duplicated()]
    m = df[df[3] == "男"]
    m = m[~m.index.duplicated()]
    POP[y] = num(t[4])
    POP40[y] = t.iloc[:, 13:26].apply(num).sum(axis=1)     # 40歳以上（40〜44 … 100歳以上）
    POPM6574[y] = m.iloc[:, 18:20].apply(num).sum(axis=1)  # 男 65〜69, 70〜74歳
SRC_JUKI = "総務省「住民基本台帳に基づく人口、人口動態及び世帯数調査」（06_健康寿命/YYMMssnen.xlsx）"

# ---------------------------------------------------------------- 1・2 特定健診受診率・特定保健指導実施率（市町村国保、保険者別）
kenshin, shido = {}, {}
unmatched = set()
for y in [2022, 2023]:
    df = pd.read_excel(ADD / f"特定健診_{y}.xlsx", sheet_name="国民健康保険", header=None, dtype=str)
    assert "特定健康診査対象者数" in str(df.iloc[4, 2]) and "特定保健指導終了者数" in str(df.iloc[4, 6])
    df = df[df[0].str.fullmatch(r"\d{8}", na=False)]
    pref = df[0].str[2:4].astype(int).map(lambda i: PREFS[i - 1])   # 保険者番号 00PPxxxx の PP＝都道府県番号
    # 「ニセコ町（後志広域連合）」のように国保を広域連合で運営する町村も町村ごとに載っているため括弧を外して照合する
    # （「最上地区広域連合」は構成町村の内訳がないため照合できず欠損）
    name = (df[1].str.replace(r"（[^）]*）", "", regex=True).str.strip()
            .str.replace("ヶ", "ケ").str.replace("梼原町", "檮原町"))
    keys = list(zip(pref, name))
    unmatched |= {k for k in keys if k not in name2code}
    idx = [name2code.get(k) for k in keys]
    d = pd.DataFrame({"A": num(df[2]).values, "B": num(df[3]).values, "C": num(df[5]).values, "D": num(df[6]).values,
                      "rateB": num(df[4]).values, "rateD": num(df[7]).values}, index=idx)
    d = d[d.index.notna()]
    kenshin[y] = d["B"] / d["A"] * 100
    # 保健指導は対象者数・終了者数が少ないと「-」（秘匿）になるため、表に載っている実施率を使う
    shido[y] = d["rateD"] * 100
if unmatched:
    print("  特定健診：照合できなかった保険者", sorted(unmatched))
put_years("特定健診受診率", kenshin)
put_years("特定保健指導実施率", shido)
SRC_TK = "厚生労働省「特定健康診査・特定保健指導の実施状況（保険者別）」国民健康保険シート（特定健診_YYYY.xlsx）"
define("特定健診受診率", "特定健康診査の受診率（市町村国保、40〜74歳）", 1, "%",
       "特定健康診査受診者数 ÷ 特定健康診査対象者数 ×100（市町村国保の被保険者）", SRC_TK, "2022〜2023年度", "あり",
       "2025・2026年度版（2024・2025年度）は代用：2024年度分は厚労省ページが掲載一時中止、2025年度分は未公表のため2023年度の値", "動かせる",
       "市町村国保の保険者は市自身で、受診勧奨・自己負担の無料化・集団健診の回数や会場で受診率を変えられる")
define("特定保健指導実施率", "特定保健指導の実施率（市町村国保）", 1, "%",
       "特定保健指導終了者数 ÷ 特定保健指導対象者数 ×100（表に載っている実施率。対象者数が少ない保険者は人数が「-」で秘匿され率のみ掲載。前年度からの継続終了者を含むため100%を超える保険者がある）",
       SRC_TK, "2022〜2023年度", "あり", "2025・2026年度版（2024・2025年度）は代用：2024年度分は厚労省ページが掲載一時中止、2025年度分は未公表のため2023年度の値", "動かせる",
       "保健指導は市（保険者）の保健師・管理栄養士が行う事業で、体制や利用勧奨で実施率を変えられる")


# ---------------------------------------------------------------- e-Stat 地域保健・健康増進事業報告（市区町村表 CSV 共通の読み方）
def hoken_csv(path):
    raw = path.read_bytes().decode("cp932")
    df = pd.read_csv(io.StringIO(raw), header=None, dtype=str)
    df = df[df[0].str.fullmatch(r"\d{4,5}", na=False)].copy()
    df.index = df[0].str.zfill(5)
    return df[~df.index.duplicated()]


# 3 大腸がん検診受診率（国保被保険者、40〜69歳）
gan, gan_tot = {}, {}
for y, f_ in [(2022, "がん検診_R04.csv"), (2023, "がん検診_R05.csv"), (2024, "がん検診_R06.csv")]:
    head = (ADD / f_).read_bytes().decode("cp932").splitlines()
    assert "大腸がん" in head[8].split(",")[12] and "国民健康保険" in head[6].split(",")[12]
    df = hoken_csv(ADD / f_)
    gan[y] = num(df[14]) / num(df[12]) * 100        # 国保再掲：受診者数 ÷ 対象者数
put_years("大腸がん検診受診率_国保", gan)
SRC_HOKEN = "厚生労働省「地域保健・健康増進事業報告」健康増進編 市区町村表"
define("大腸がん検診受診率_国保", "大腸がん検診の受診率（市町村国保の被保険者、40〜69歳）", 1, "%",
       "大腸がん検診受診者数 ÷ 対象者数 ×100（いずれも（再掲）国民健康保険の被保険者、40〜69歳。"
       "住民全体の率は職域検診を含まず低く出るため、国保再掲を使う。「…」は欠損）",
       SRC_HOKEN + " 第20-1表（がん検診_R0N.csv）", "2022〜2024年度", "あり", sub_note(gan), "動かせる",
       "がん検診は市の健康増進事業で、受診勧奨・個別通知・自己負担額・実施機関の数で受診率を変えられる")

# 4 集団健康教育の参加延人員（40歳以上人口千人あたり）
kyoiku = {}
for y, f_ in [(2022, "健康教育_R04.csv"), (2023, "健康教育_R05.csv"), (2024, "健康教育_R06.csv")]:
    head = (ADD / f_).read_bytes().decode("cp932").splitlines()
    assert "参加延人員" in head[6].split(",")[9] and "総数" in head[7].split(",")[9]
    df = hoken_csv(ADD / f_)
    kyoiku[y] = num(df[9]) / POP40[y] * 1000
put_years("集団健康教育参加率", kyoiku)
define("集団健康教育参加率", "40歳以上人口千人あたり 集団健康教育の参加延人員", 1, "人/40歳以上千人",
       "集団健康教育（一般・歯周疾患・ロコモ・COPD・病態別・薬）の参加延人員（総数。「-」は0）÷ 40歳以上住基人口（翌年1月1日）×1000",
       SRC_HOKEN + " 第3表（健康教育_R0N.csv）", "2022〜2024年度", "あり", sub_note(kyoiku), "動かせる",
       "健康増進法に基づく市の健康教育事業で、開催回数・テーマ・会場を市が決められる")

# ---------------------------------------------------------------- 5 男性65〜74歳の要介護（要支援）認定率（介護保険事業状況報告 月報 6月末）
kaigo = {}
for y in YEARS:
    kg = pd.read_excel(RAW / "06_健康寿命" / f"{y % 100:02d}06-h2-2.xlsx", header=None, dtype=str)
    assert "65歳以上70歳未満" in str(kg.iloc[3, 18]) and "70歳以上75歳未満" in str(kg.iloc[3, 26])
    assert str(kg.iloc[5, 25]).strip() == "計" and str(kg.iloc[5, 33]).strip() == "計"
    kg = kg.iloc[7:]
    idx = [name2code.get((p, str(n).replace("ヶ", "ケ"))) for p, n in zip(kg[0], kg[1])]
    s = pd.Series((num(kg[25]) + num(kg[33])).values, index=idx)
    s = s[s.index.notna()]
    kaigo[y] = s / POPM6574[y] * 100
put_years("男性65_74歳要介護認定率", kaigo)
define("男性65_74歳要介護認定率", "男性65〜74歳の要介護（要支援）認定率", -1, "%",
       "第1号被保険者のうち男65〜69歳・70〜74歳の要支援1〜要介護5の認定者数（各年6月末）÷ 男65〜74歳の住基人口（翌年1月1日）×100。"
       "介護保険を広域連合・一部事務組合で運営する市町村は保険者単位の値しかないため欠損",
       "厚生労働省「介護保険事業状況報告（暫定）」月報 第2-2表（06_健康寿命/YY06-h2-2.xlsx）＋" + SRC_JUKI,
       "2022〜2025年（各年6月末）", "あり", "なし", "動かせない",
       "健康状態の結果に近い指標（健康寿命KPIの材料と同じ統計）で、介護予防の効果が出るまで時間がかかり短期の施策では動きにくい")

# ---------------------------------------------------------------- 6 国保の医療費の地域差指数（年齢調整後、医療費の地域差分析 表30）
iryo = {}
for y, f_ in [(2022, "医療費地域差_R04.xlsx"), (2023, "医療費地域差_R05.xlsx")]:
    df = pd.read_excel(ADD / f_, sheet_name="30", header=None, dtype=str)
    assert "地域差指数" in str(df.iloc[3, 12]) and str(df.iloc[4, 12]).strip() == "計"
    df = df[df[3].str.fullmatch(r"\d{4,5}", na=False)]
    df = df[df[0].fillna("").str.strip() != "*"]   # 「*」＝市区町村単位の医療費が把握できず広域の値を載せている
    s = pd.Series(num(df[12]).values, index=df[3].str.zfill(5).values)
    iryo[y] = s[~s.index.duplicated(keep="last")]   # 政令市は末尾の市全体の行
put_years("国保医療費地域差指数", iryo)
define("国保医療費地域差指数", "市町村国保の一人当たり年齢調整後医療費の地域差指数", -1, "指数（全国=1）",
       "一人当たり年齢調整後医療費 ÷ 全国の一人当たり医療費（診療種別計）。「*」の市区町村（市区町村単位の医療費が把握できず広域の値を掲載。2023年度は沼津市にも付いている）は欠損",
       "厚生労働省「医療費の地域差分析」基礎データ 表30 市区町村別データ 市町村国民健康保険（医療費地域差_R0N.xlsx）",
       "2022〜2023年度", "あり",
       "2025・2026年度版（2024・2025年度）は代用：2024年度は電算処理分のみの公表で市区町村別の表がなく、2025年度は未公表のため2023年度の値", "動かせない",
       "医療提供体制・受療行動・疾病構造で決まり、市の施策（重症化予防等）の効果は小さく時間もかかる")


# ---------------------------------------------------------------- 7・8 一般診療所数・医師数（統計でみる市区町村のすがた I）
def sugata(path, colmap):
    df = pd.read_excel(path, header=None, skiprows=10, dtype=str)
    df["code"] = df.iloc[:, -1].str.strip()
    df = df[df["code"].str.fullmatch(r"\d{5}", na=False)].set_index("code")
    df = df[~df.index.duplicated()]
    return pd.DataFrame({name: num(df.iloc[:, i]) for i, name in colmap.items()})


SRC_SUGATA = "総務省統計局「統計でみる市区町村のすがた」"
clinic = {}
for edition, y in [("2025", 2022), ("2026", 2023)]:
    hdr = pd.read_excel(ADD / f"{edition}-i.xls", header=None, dtype=str, nrows=10)
    assert str(hdr.iloc[7, 11]).strip() == "I5102" and str(hdr.iloc[9, 11]).strip() == str(y)
    i = sugata(ADD / f"{edition}-i.xls", {11: "診療所"})
    clinic[y] = i["診療所"] / POP[y] * 1e5   # 診療所数は10月1日現在 → 分母は翌年1月1日の住基人口
put_years("人口あたり一般診療所数", clinic)
define("人口あたり一般診療所数", "人口10万人あたり一般診療所数", 1, "所/10万人",
       "一般診療所数（I5102、10月1日現在）÷ 住基人口（翌年1月1日）×10万",
       SRC_SUGATA + "2025・2026 I 健康・医療（YYYY-i.xls。元は厚生労働省「医療施設調査」）", "2022・2023（すがたの年次表記）",
       "あり", "2025・2026年度版（2024・2025年）は未公表のため2023年の値で代用", "動かせない",
       "民間の開業で決まり、市ができるのは誘致・へき地診療所の運営程度で、全国比較で値を大きく変えにくい")

hdr = pd.read_excel(ADD / "2026-i.xls", header=None, dtype=str, nrows=10)
assert str(hdr.iloc[7, 13]).strip() == "I6100" and str(hdr.iloc[9, 13]).strip() == "2022"
doc = sugata(ADD / "2026-i.xls", {13: "医師"})["医師"] / POP[2022] * 1e5
put_years("人口あたり医師数", {2022: doc})
define("人口あたり医師数", "人口10万人あたり医師数（従業地）", 1, "人/10万人",
       "医師数（I6100、2022年12月31日現在、従業地）÷ 住基人口（2023年1月1日）×10万",
       SRC_SUGATA + "2026 I 健康・医療（2026-i.xls。元は厚生労働省「医師・歯科医師・薬剤師統計」）", "2022",
       "なし（1時点）", "全年度版に2022年の値", "動かせない",
       "医師の配置は病院・大学・県の医療計画で決まり、市の施策で変えにくい")

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
panel.round(4).to_csv(OUT / "06_追加変数_健康状態.csv", index=False, encoding="utf-8-sig")
defs = pd.DataFrame([DEFS[c] for c in cols])
defs.to_csv(OUT / "06_追加変数_健康状態_定義.csv", index=False, encoding="utf-8-sig")

print(panel.shape)
miss = panel.groupby("年度版")[cols].apply(lambda d: d.isna().sum()).T
print("欠損件数（年度版別, 全1,741）"); print(miss.to_string())
w = panel[panel["市区町村コード"].isin(["30206"])].set_index(["市区町村コード", "年度版"])
print(w.round(3).T.to_string())
