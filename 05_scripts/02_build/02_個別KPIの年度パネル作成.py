"""年度ごとに値がとれる個別KPIを、2022〜2025年分そろえる（年度パネル）。

幸福度データの「Y年度版」には、個別KPIの「Y−1年（暦年・年度）」の値を対応させる（調査より前の環境）。
  例：2026年度版 ← 2025年の値。まだ公表されていない年は、最新年の値で代用し「代用」列に記録する。
人口あたりの分母は、その年の翌年1月1日の住民基本台帳人口（≒その年の年末人口）。

入力 : 04_data/01_raw/（02,03,05,06,07,08,10,12）
出力 : 04_data/02_processed/02_市区町村別_個別KPI_年度別.csv（縦持ち：市区町村コード, データ年, 年度版, KPI, 値, 代用）
       04_data/02_processed/02_市区町村別_個別KPI_年度別_横.csv（市区町村コード×年度版、KPIが列）
"""
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
RAW = BASE / "04_data" / "01_raw"
OUT = BASE / "04_data" / "02_processed"
YEARS = [2022, 2023, 2024, 2025]  # データ年（→ 年度版 2023〜2026）


def num(s):
    return pd.to_numeric(s, errors="coerce")


master = pd.read_csv(OUT / "01_市区町村別_個別KPI.csv", dtype={"市区町村コード": str})[["市区町村コード", "都道府県", "市区町村", "区分"]]
codes = master["市区町村コード"]
name2code = {(p, n): c for c, p, n in zip(master["市区町村コード"], master["都道府県"], master["市区町村"])}

# 政令市の区 → 市（国勢調査の地域一覧の並びから作る：市の行の直後に区が並ぶ）
cen = pd.read_excel(RAW / "02_国勢調査2020" / "b02_07.xlsx", header=None, skiprows=12, dtype=str, usecols=[0, 1, 2, 7])
cen = cen[(cen[0] == "0_国籍総数") & (cen[1] == "0_総数")]
ward2city, cur = {}, None
for k, c in zip(cen[2], cen[7]):
    if k == "1":
        cur = c
    elif k == "0" and cur and not c.startswith("131"):
        ward2city[c] = cur
ward2city.update({"22138": "22130", "22139": "22130", "22140": "22130"})  # 浜松市の新3区（2024年〜）

records = []  # (code, データ年, KPI, 値, 代用元の年 or None)


def add(series, year, kpi, src_year=None):
    s = series.reindex(codes.values)
    for c, v in s.items():
        records.append((c, year, kpi, v, src_year))


# ---------------------------------------------------------------- 住基人口（各年1月1日）
def juki(file):
    df = pd.read_excel(RAW / "06_健康寿命" / file, header=None, skiprows=3, dtype=str)
    df = df[df[0].str.fullmatch(r"\d{6}", na=False)].copy()
    df["code"] = df[0].str[:5]
    return df


POP, JUKI = {}, {}
for y, f in [(2022, "2304ssnen.xlsx"), (2023, "2404ssnen.xlsx"), (2024, "2504ssnen.xlsx"), (2025, "2604ssnen.xlsx")]:
    df = juki(f)
    JUKI[y] = df
    t = df[df[3] == "計"].set_index("code")
    POP[y] = num(t[4])
    add(t.iloc[:, 18:26].apply(num).sum(axis=1) / num(t[4]) * 100, y, "高齢化率")

# ---------------------------------------------------------------- 08 転入超過割合
for y in YEARS:
    f = next((RAW / "08_住民基本台帳人口移動報告").glob(f"b01103s_*_{y}.xlsx"))
    df = pd.read_excel(f, header=None, skiprows=6, dtype=str)
    df = df[df[2] == "移動者"]
    s = num(df.set_index(df[5].str.zfill(5))[7])
    s = s[~s.index.duplicated()]
    add(s / POP[y] * 100, y, "転入超過割合")

# ---------------------------------------------------------------- 07 人口あたり自殺者数
for y in YEARS:
    d = RAW / "07_自殺の基礎資料" / f"R{y - 2018}_自殺日集計"
    f = next(d.glob("*A7*"))
    df = pd.read_excel(f, sheet_name=0, header=None, skiprows=8, dtype=str)
    df = df[df[1].str.fullmatch(r"\d{5,6}", na=False)]
    s = num(df.set_index(df[1].str.zfill(6).str[:5])[4])
    s = s[~s.index.duplicated()].reindex(codes.values).fillna(0)  # 表に載っていない＝0人
    add(s / POP[y] * 1e5, y, "人口あたり自殺者数")

# ---------------------------------------------------------------- 05 地方財政（年度）
fin = RAW / "05_地方財政"


def shihyo(r):
    f = next(fin.glob(f"R{r:02d}_全市町村の主要財政指標_*.xlsx"))
    df = pd.read_excel(f, header=1, dtype=str)
    df = df[df["団体コード"].str.fullmatch(r"\d{6}", na=False)]
    return df.set_index(df["団体コード"].str[:5])


def kessan(r, kind, part, col):
    f = next(fin.glob(f"R{r:02d}_市町村別決算状況調_{kind}_{part}_*.xlsx"))
    df = pd.read_excel(f, header=None, dtype=str)
    df = df[df[14].str.fullmatch(r"\d{6}", na=False)]
    return num(df.set_index(df[14].str[:5])[col])


latest_fy = max(int(re.search(r"R(\d\d)_全市町村", p.name).group(1)) for p in fin.glob("R*_全市町村の主要財政指標_*.xlsx")) + 2018
for y in YEARS:
    fy = min(y, latest_fy)
    r = fy - 2018
    sh = shihyo(r)
    src = fy if fy != y else None
    add(num(sh["財政力指数"]), y, "財政力指数", src)
    add(num(sh["実質公債費比率"]), y, "実質公債費比率", src)
    edu = pd.concat([kessan(r, k, "03目的別歳出内訳", 57) for k in ("都市別", "町村別")])
    tot = pd.concat([kessan(r, k, "01概況", 40) for k in ("都市別", "町村別")])
    add(edu / tot * 100, y, "歳出総額の教育費割合", src)

# ---------------------------------------------------------------- 06 健康寿命（近似）：生命表2020 × 要介護2以上の割合（その年の6月）
life = {}
xls = pd.ExcelFile(RAW / "06_健康寿命" / "ckts-lifetable2020.xlsx")
for sh in [s for s in xls.sheet_names if s.startswith("生命表")]:
    t = pd.read_excel(xls, sh, header=None, dtype=str)
    cur, sex = None, None
    for _, r in t.iterrows():
        a = str(r[0]).strip()
        if a.startswith("表"):
            cur = a[1:].zfill(5)
            life[cur] = {"男": [], "女": []}
        elif a in ("男", "女"):
            sex = a
        elif cur and sex and re.match(r"\d", a) and life[cur] is not None:
            try:
                life[cur][sex].append((a, float(r[2]), float(r[4])))
            except ValueError:
                life[cur] = None
AGES = ["0", "5", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55", "60", "65", "70", "75", "80", "85", "90", "95", "100"]
BLOCKS = {"65": 18, "70": 26, "75": 34, "80": 42, "85": 50, "90": 58, "2号": 66}
for y in YEARS:
    jk = JUKI[y]
    pop = {(c, s): dict(zip(AGES, num(pd.Series(r.values[5:26])).tolist())) for c, s, (_, r) in zip(jk["code"], jk[3], jk.iterrows())}
    for sex, tbl in (("男", "h2-2"), ("女", "h2-3")):
        kg = pd.read_excel(RAW / "06_健康寿命" / f"{y % 100:02d}06-{tbl}.xlsx", header=None, skiprows=7)
        res = {}
        for _, r in kg.iterrows():
            code = name2code.get((r[0], r[1]))
            if code is None or life.get(code) is None or (code, sex) not in pop:
                continue
            p = pop[(code, sex)]
            care = {k: sum(float(r[s + o]) for o in range(3, 7)) for k, s in BLOCKS.items()}
            rate = {k: care[k] / p[k] if p[k] else np.nan for k in ["65", "70", "75", "80", "85"]}
            p90 = p["90"] + p["95"] + p["100"]
            rate["90"] = rate["95"] = care["90"] / p90 if p90 else np.nan
            p40 = sum(p[a] for a in ["40", "45", "50", "55", "60"])
            for a in ["40", "45", "50", "55", "60"]:
                rate[a] = care["2号"] / p40 if p40 else np.nan
            hl = 0.0
            for lab, _, nL in life[code][sex]:
                st = re.match(r"\s*(\d+)", lab).group(1)
                st = "0" if st in ("0", "1") else st
                hl += nL * (1 - min(rate.get(st, 0.0), 1.0))
            res[code] = hl / life[code][sex][0][1]
        add(pd.Series(res), y, f"健康寿命_{sex}性_近似")

# ---------------------------------------------------------------- 03 幼稚園数・高等学校数（5月1日）÷ 可住地面積
d3 = RAW / "03_社会人口統計体系"


def sugata(file, cols):
    df = pd.read_excel(d3 / file, header=None, skiprows=10, dtype=str)
    df["code"] = df.iloc[:, -1].str.strip()
    df = df[df["code"].str.fullmatch(r"\d{5}", na=False)].set_index("code")
    return pd.DataFrame({n: num(df.iloc[:, i]) for i, n in cols.items()})


def to_city(s):
    """政令市の区の値を市にまとめる（区だけが載っている表用）。"""
    s = s.copy()
    w = s[s.index.isin(ward2city)]
    city = w.groupby(w.index.map(ward2city)).sum()
    return pd.concat([s[~s.index.isin(ward2city)], city]).groupby(level=0).sum()


def gakko2025(file):
    """学校基本調査2025：都道府県ごとのシート、A列=県内3桁コード、C列=学校数（政令市は区のみ）。"""
    x = pd.ExcelFile(d3 / file)
    out = {}
    for i, sh in enumerate(x.sheet_names[1:], 1):
        df = pd.read_excel(x, sh, header=None, skiprows=6, dtype=str)
        df = df[df[0].str.fullmatch(r"\d{3}", na=False)]
        for c3, v in zip(df[0], df[2]):
            out[f"{i:02d}{c3}"] = v
    return to_city(num(pd.Series(out)).fillna(0))


area = {2022: sugata("2024-b.xls", {11: "可住地"})["可住地"], 2023: sugata("2025-b.xls", {11: "可住地"})["可住地"],
        2024: sugata("2026-b.xls", {11: "可住地"})["可住地"]}
area[2025] = area[2024]  # 2025年の可住地面積は未公表 → 2024年で代用（年ごとの変化はごく小さい）
school = {y: sugata(f, {10: "幼稚園", 18: "高校"}) for y, f in [(2022, "2024-e.xls"), (2023, "2025-e.xls"), (2024, "2026-e.xls")]}
school[2025] = pd.DataFrame({"幼稚園": gakko2025("ey0323_1_2025.xlsx"), "高校": gakko2025("ey0328_1_2025.xlsx")})
for y in YEARS:
    add(school[y]["幼稚園"] / area[y], y, "可住地面積あたり幼稚園数")
    add(school[y]["高校"] / area[y], y, "可住地面積あたり高等学校数")

# ---------------------------------------------------------------- 10 人口あたりNPOの数（各年12月31日時点の現存法人）
z = zipfile.ZipFile(RAW / "10_NPO法人" / "gyousei_000.zip")
npo = pd.read_csv(z.open([n for n in z.namelist() if n.endswith(".csv")][0]), encoding="cp932", dtype=str)
npo = npo[npo["主たる事務所の所在地"].notna()]
est = pd.to_datetime(npo["法人設立認証年月日"], errors="coerce").fillna(pd.to_datetime(npo["設立年月日"], errors="coerce"))
ymd = npo["解散情報"].str.extract(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
dis = pd.to_datetime(ymd[0] + "-" + ymd[1] + "-" + ymd[2], errors="coerce")
PREFS = sorted(master["都道府県"].unique(), key=len, reverse=True)
city2pref = {"札幌市": "北海道", "仙台市": "宮城県", "さいたま市": "埼玉県", "千葉市": "千葉県", "横浜市": "神奈川県",
             "川崎市": "神奈川県", "相模原市": "神奈川県", "新潟市": "新潟県", "静岡市": "静岡県", "浜松市": "静岡県",
             "名古屋市": "愛知県", "京都市": "京都府", "大阪市": "大阪府", "堺市": "大阪府", "神戸市": "兵庫県",
             "岡山市": "岡山県", "広島市": "広島県", "北九州市": "福岡県", "福岡市": "福岡県", "熊本市": "熊本県"}
names = {p: sorted(((n, c) for c, pp, n in zip(master["市区町村コード"], master["都道府県"], master["市区町村"]) if pp == p),
                   key=lambda x: -len(x[0])) for p in PREFS}


def locate(pref, addr):
    addr = str(addr).replace(" ", "").replace("　", "")
    if addr.startswith(pref):
        addr = addr[len(pref):]
    addr = re.sub(r"^.{1,4}?郡", "", addr)
    return next((c for n, c in names.get(pref, []) if addr.startswith(n)), None)


npo["code"] = [locate(city2pref.get(a, a), b) for a, b in zip(npo["所轄庁"], npo["主たる事務所の所在地"])]
for y in YEARS:
    end = pd.Timestamp(f"{y}-12-31")
    alive = (est.isna() | (est <= end)) & (dis.isna() | (dis > end))  # 認証日が不明な法人は古い法人とみなす
    cnt = npo[alive]["code"].value_counts()
    add(cnt.reindex(codes.values).fillna(0) / POP[y] * 1e5, y, "人口あたりNPOの数")

# ---------------------------------------------------------------- 12 人口あたり公園面積（決算年度末）
pk = pd.read_excel(RAW / "12_公共施設状況調" / "市町村経年比較表_H18-R06_001068878.xlsx", sheet_name="AFAHO14H1030",
                   header=None, skiprows=7, dtype=str)
pk = pk[pk[2].str.fullmatch(r"\d{6}", na=False)]
pk_years = sorted(int(v) for v in pk[0].str.strip().unique() if str(v).isdigit())
for y in YEARS:
    fy = min(y, max(pk_years))
    d = pk[pk[0].str.strip() == str(fy)]
    a = sum(num(d[c].replace("-", "0")).fillna(0) for c in (12, 14, 20, 22))
    s = pd.Series(a.values, index=d[2].str[:5].values)
    s = s[~s.index.duplicated()]
    add(s / POP[y], y, "人口あたり公園面積", fy if fy != y else None)

# ---------------------------------------------------------------- 出力
panel = pd.DataFrame(records, columns=["市区町村コード", "データ年", "KPI", "値", "代用元の年"])
panel["年度版"] = panel["データ年"] + 1
panel["代用"] = panel["代用元の年"].notna()
panel = panel.merge(master, on="市区町村コード", how="left")
panel.to_csv(OUT / "02_市区町村別_個別KPI_年度別.csv", index=False, encoding="utf-8-sig")
wide = panel.pivot_table(index=["市区町村コード", "年度版"], columns="KPI", values="値").reset_index()
wide.to_csv(OUT / "02_市区町村別_個別KPI_年度別_横.csv", index=False, encoding="utf-8-sig")

summ = panel.groupby(["KPI", "データ年"])["値"].agg(["count", "median"]).unstack("データ年")
print(summ.round(2).to_string())
print(panel[panel["代用"]].groupby(["KPI", "データ年"])["代用元の年"].first().to_string())
w = wide[wide["市区町村コード"].isin(["30201", "30206"])].set_index(["市区町村コード", "年度版"])
print(w.round(2).T.to_string())
