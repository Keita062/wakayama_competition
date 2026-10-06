"""04_data/01_raw の原本から、市区町村 × 個別KPI の1枚の表を作る。

入力 : 04_data/01_raw/NN_出典名/   （05_scripts/01_download/NN_出典名.py で取得）
出力 : 04_data/02_processed/01_市区町村別_個別KPI.csv
       04_data/02_processed/01_市区町村別_個別KPI_定義.csv（列ごとの出典・計算式・年）

行   : 全国の市区町村（政令市は市全体の1行、東京23区は区ごと。政令市の区は含めない）＝1,741行
キー : 5桁の市区町村コード（令和2年国勢調査の地域コード）
関数名の番号は 04_data/01_raw のフォルダ番号と対応している。
"""
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf

BASE = Path(__file__).resolve().parents[2]
RAW = BASE / "04_data" / "01_raw"
OUT = BASE / "04_data" / "02_processed"

PREFS = ["北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県",
         "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県",
         "岐阜県", "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県",
         "鳥取県", "島根県", "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
         "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"]

# 列名 → (分野, 出典フォルダ, 計算式, 年)
DEFS = {}


def define(col, field, src, formula, year):
    DEFS[col] = (field, src, formula, year)


def num(s):
    return pd.to_numeric(s, errors="coerce")


def code5(s):
    """団体コード（6桁・チェックディジット付き、または先頭0が落ちた数値）を5桁にそろえる。"""
    return s.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()


def read_census(path, id_row, label_row, data_row):
    """国勢調査のe-Stat表：id列は id_row の見出し、値の列は label_row の見出しで名前を付ける。"""
    raw = pd.read_excel(path, header=None, dtype=str)
    ids = raw.iloc[id_row].tolist()
    labels = raw.iloc[label_row].tolist()
    cols = [l if isinstance(l, str) and l.strip() else ids[i] for i, l in enumerate(labels)]
    df = raw.iloc[data_row:].copy()
    df.columns = cols
    name_col = "地域名"
    df = df[~df[name_col].astype(str).str.contains("旧：")]
    if "2020年_地域コード" in df.columns:
        df["code"] = df["2020年_地域コード"].str[:5]
    else:
        df["code"] = df[name_col].str[:5]
    return df


# ---------------------------------------------------------------- 02 国勢調査2020（行の土台・人口）
def base_and_census():
    d = RAW / "02_国勢調査2020"

    pop = read_census(d / "b02_07.xlsx", 11, 9, 12)
    pop = pop[(pop["国籍総数か日本人"] == "0_国籍総数") & (pop["男女"] == "0_総数")]
    kind = pop["地域識別コード"]
    is_ku23 = (kind == "0") & pop["code"].str.startswith("131")
    keep = kind.isin(["1", "2", "3"]) & (pop["code"] != "13100") | is_ku23
    pop = pop[keep]
    kind = pop["地域識別コード"]
    base = pd.DataFrame({
        "市区町村コード": pop["code"].values,
        "都道府県": pop["2020年_都道府県"].str.split("_").str[1].values,
        "市区町村": pop["地域名"].str.split("_", n=1).str[1].values,
        "区分": kind.map({"1": "政令市", "2": "市", "3": "町村", "0": "特別区"}).values,
        "人口": num(pop["00_総数"]).values,
    }).set_index("市区町村コード")
    define("人口", "類型", "02_国勢調査2020", "b02_07 総人口", "2020")

    # 高齢化率は住基人口(2024/1)でPDFの値と一致した（国勢調査2020では一致しない）
    jk = pd.read_excel(RAW / "06_健康寿命" / "2404ssnen.xlsx", header=None, skiprows=3, dtype=str)
    jk = jk[jk[0].str.fullmatch(r"\d{6}", na=False) & (jk[3] == "計")]
    jk = jk.set_index(jk[0].str[:5])
    base["高齢化率"] = jk.iloc[:, 18:26].apply(num).sum(axis=1) / num(jk[4]) * 100
    define("高齢化率", "類型", "06_健康寿命（住基人口）", "65歳以上人口 ÷ 総人口 ×100（%）", "2024/1/1")

    ind = read_census(d / "c05_03.xlsx", 9, 7, 10)
    ind = ind[ind["男女"] == "0_総数"]
    tot = ind[ind["産業"] == "0_総数"].set_index("code")["0_総数"]
    first = ind[ind["産業"] == "R1_（再掲）第1次産業"].set_index("code")["0_総数"]
    base["第1次産業就業者割合"] = num(first) / num(tot) * 100
    define("第1次産業就業者割合", "類型", "02_国勢調査2020", "第1次産業就業者 ÷ 就業者総数 ×100（%）", "2020")

    hh = read_census(d / "b27_04.xlsx", 9, 7, 10)
    hh = hh[hh.iloc[:, 3] == "0_総数"].set_index("code")
    total = num(hh["0_総数"])
    base["高齢単身世帯割合"] = num(hh["R7_（再掲）65歳以上の単独世帯"]) / total * 100
    base["拡大家族世帯割合"] = num(hh["12_核家族以外の世帯"]) / total * 100
    define("高齢単身世帯割合", "地域とのつながり", "02_国勢調査2020", "65歳以上の単独世帯 ÷ 一般世帯総数 ×100（%）", "2020")
    define("拡大家族世帯割合", "地域とのつながり", "02_国勢調査2020", "核家族以外の世帯 ÷ 一般世帯総数 ×100（%）", "2020")

    lab = read_census(d / "c01_02.xlsx", 9, 7, 10)
    lab = lab[(lab["男女"] == "0_総数") & (lab["年齢"] == "00_総数")].set_index("code")
    unemp = num(lab["12_完全失業者"])
    base["完全失業者数_人口比"] = unemp / base["人口"] * 100
    base["完全失業率"] = unemp / num(lab["1_労働力人口"]) * 100
    define("完全失業者数_人口比", "自己効力感", "02_国勢調査2020", "完全失業者 ÷ 人口 ×100（%）", "2020")
    define("完全失業率", "雇用・所得", "02_国勢調査2020", "完全失業者 ÷ 労働力人口 ×100（%）", "2020")

    mar = read_census(d / "b04_03.xlsx", 10, 8, 11)
    mar = mar[(mar["国籍総数か日本人"] == "0_国籍総数") & (mar["男女"] == "0_総数")]
    m = mar.pivot_table(index="code", columns="配偶関係", values="00_総数", aggfunc="first").apply(num)
    known = m["0_総数"] - m["5_配偶関係「不詳」"].fillna(0)  # 不詳「-」＝0人
    base["既婚者割合"] = (1 - m["1_未婚"] / known) * 100
    define("既婚者割合", "地域とのつながり", "02_国勢調査2020", "（1 − 未婚 ÷（15歳以上人口 − 配偶関係不詳））×100（%）", "2020")
    return base


# ---------------------------------------------------------------- 01 都市モニタリングシート
def toshi_monitoring(base):
    f = RAW / "01_都市モニタリングシート" / "都市モニタリングシート_全体表_001406670.xlsx"
    cols = {"PE": "医療施設徒歩圏人口カバー率", "PF": "福祉施設徒歩圏人口カバー率", "PG": "商業施設徒歩圏人口カバー率",
            "PH": "駅バス停徒歩圏人口カバー率", "QB": "人口あたり小型車走行キロ", "QQ": "保育所徒歩圏0_4歳人口カバー率",
            "QW": "歩道設置率", "RC": "公園緑地徒歩圏人口カバー率"}
    df = pd.read_excel(f, sheet_name="R6年全体表", header=None, skiprows=9, dtype=str,
                       usecols=",".join(["H"] + list(cols)))
    df.columns = ["code"] + list(cols.values())
    df = df[df["code"].str.fullmatch(r"\d{5}", na=False)].set_index("code")
    meta = {"医療施設徒歩圏人口カバー率": ("医療・福祉", "指標273 PE列（%）", "2020"),
            "福祉施設徒歩圏人口カバー率": ("医療・福祉", "指標274 PF列（%）", "2021"),
            "商業施設徒歩圏人口カバー率": ("買物・飲食", "指標275 PG列（%）", "2020"),
            "駅バス停徒歩圏人口カバー率": ("移動・交通", "指標276 PH列（%）", "駅2023・バス停2022"),
            "人口あたり小型車走行キロ": ("移動・交通", "指標296 QB列（台キロ/人）", "2021"),
            "保育所徒歩圏0_4歳人口カバー率": ("子育て", "指標311 QQ列（%）", "2015"),
            "歩道設置率": ("公共空間", "指標317 QW列（%）", "2021"),
            "公園緑地徒歩圏人口カバー率": ("公共空間", "指標323 RC列（%）", "公園2011・人口2020")}
    for c, (field, formula, year) in meta.items():
        base[c] = num(df[c])
        define(c, field, "01_都市モニタリングシート", formula, year)


# ---------------------------------------------------------------- 03 社会人口統計体系（＋経済センサス第6-1表）
def sugata(path, colmap):
    df = pd.read_excel(path, header=None, skiprows=10, dtype=str)
    df["code"] = df.iloc[:, -1].str.strip()
    df = df[df["code"].str.fullmatch(r"\d{5}", na=False)].set_index("code")
    return pd.DataFrame({name: num(df.iloc[:, i]) for i, name in colmap.items()})


def shakai_jinko(base):
    d = RAW / "03_社会人口統計体系"
    area = sugata(d / "2026-b.xls", {10: "総面積", 11: "可住地面積"})
    edu = sugata(d / "2026-e.xls", {10: "幼稚園数", 18: "高等学校数"})
    base["総面積_km2"] = area["総面積"]
    base["可住地面積_km2"] = area["可住地面積"]
    base["人口密度"] = base["人口"] / base["総面積_km2"]
    base["可住地面積割合"] = base["可住地面積_km2"] / base["総面積_km2"] * 100
    define("人口密度", "類型", "02・03", "人口 ÷ 総面積（人/km²）", "人口2020・面積2024")
    define("可住地面積割合", "類型", "03_社会人口統計体系", "可住地面積 ÷ 総面積 ×100（%）", "2024")

    ec = pd.read_excel(d / "b1_006_1.xlsx", header=None, skiprows=9, dtype=str)
    ec = ec[ec[4] == "76_飲食店"]
    ec = ec.assign(code=ec[1].str[:5]).drop_duplicates("code").set_index("code")
    base["可住地面積あたり飲食店数"] = num(ec[5]) / base["可住地面積_km2"]
    define("可住地面積あたり飲食店数", "買物・飲食", "03_社会人口統計体系", "飲食店の事業所数（経済センサス2021 第6-1表）÷ 可住地面積（店/km²）", "2021/2024")

    base["可住地面積あたり幼稚園数"] = edu["幼稚園数"] / base["可住地面積_km2"]
    base["可住地面積あたり高等学校数"] = edu["高等学校数"] / base["可住地面積_km2"]
    define("可住地面積あたり幼稚園数", "子育て", "03_社会人口統計体系", "幼稚園数（E1101）÷ 可住地面積（園/km²）", "2024")
    define("可住地面積あたり高等学校数", "初等・中等教育", "03_社会人口統計体系", "高等学校数（E4101）÷ 可住地面積（校/km²）", "2024")


# ---------------------------------------------------------------- 04 住宅・土地統計調査2023
def jutaku(base):
    df = pd.read_excel(RAW / "04_住宅土地統計調査2023" / "e010_4.xlsx", header=None, skiprows=7, dtype=str)
    df["code"] = df[1].str[:5]
    tot = df[(df[2] == "0_総数") & (df[3] == "0_総数") & (df[4] == "0_総数")].drop_duplicates("code").set_index("code")
    own = df[(df[2] == "0_総数") & (df[3] == "1_持ち家") & (df[4] == "1_一戸建")].drop_duplicates("code").set_index("code")
    base["一戸建の持ち家の割合"] = num(own[5]) / num(tot[5]) * 100
    base["住宅当たり延べ面積"] = num(tot[10])
    define("一戸建の持ち家の割合", "住宅環境", "04_住宅土地統計調査2023", "持ち家かつ一戸建の住宅数 ÷ 住宅総数 ×100（%）。市と人口1.5万人以上の町村のみ", "2023")
    define("住宅当たり延べ面積", "住宅環境", "04_住宅土地統計調査2023", "1住宅当たり延べ面積（m²）", "2023")


# ---------------------------------------------------------------- 05 地方財政
def chiho_zaisei(base):
    d = RAW / "05_地方財政"
    def shihyo(name):
        raw = pd.read_excel(d / name, header=None, dtype=str)
        h = raw.index[raw[0] == "団体コード"][0]
        df = raw.iloc[h + 1:]
        df.columns = raw.iloc[h]
        df = df[df["団体コード"].str.fullmatch(r"\d{6}", na=False)]
        return df.set_index(df["団体コード"].str[:5])

    # 年度はPDFの値と照合して決めた（財政力指数＝R5、実質公債費比率＝R3）
    base["財政力指数"] = num(shihyo("R05_全市町村の主要財政指標_000983094.xlsx")["財政力指数"])
    base["実質公債費比率"] = num(shihyo("R03_全市町村の主要財政指標_000849999.xlsx")["実質公債費比率"])
    define("財政力指数", "類型", "05_地方財政", "主要財政指標一覧（R5）", "2023年度")
    define("実質公債費比率", "地域行政", "05_地方財政", "主要財政指標一覧（R3）（%）", "2021年度")

    def kessan(name, col):
        df = pd.read_excel(d / name, header=None, dtype=str)
        df = df[df[14].str.fullmatch(r"\d{6}", na=False)]
        return num(df.set_index(df[14].str[:5])[col])

    edu = pd.concat([kessan("R03_市町村別決算状況調_都市別_03目的別歳出内訳_000871020.xlsx", 57),
                     kessan("R03_市町村別決算状況調_町村別_03目的別歳出内訳_000871025.xlsx", 57)])
    total = pd.concat([kessan("R03_市町村別決算状況調_都市別_01概況_000871018.xlsx", 40),
                       kessan("R03_市町村別決算状況調_町村別_01概況_000871023.xlsx", 40)])
    base["歳出総額の教育費割合"] = edu / total * 100
    define("歳出総額の教育費割合", "子育て", "05_地方財政", "目的別歳出「十 教育費」÷ 歳出総額 ×100（%）", "2021年度")


# ---------------------------------------------------------------- 06 健康寿命（近似）
def kenko_jumyo(base):
    """サリバン法による近似：要介護2以上を「不健康」とし、生命表の定常人口 nLx に（1−不健康割合）を掛けて合計する。
    65歳以上は5歳階級別の要介護2〜5認定者数 ÷ 住基人口、40〜64歳は第2号の要介護2〜5認定者数 ÷ 40〜64歳人口、
    40歳未満は不健康割合0とする。介護保険を広域連合で運営する市町村は保険者単位の値がないため欠損。"""
    d = RAW / "06_健康寿命"

    # 生命表：表NNNNN ごとに男女の nLx を読む
    life = {}
    xls = pd.ExcelFile(d / "ckts-lifetable2020.xlsx")
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
                    life[cur][sex].append((a, float(r[2]), float(r[4])))  # 年齢, lx, nLx
                except ValueError:  # 「…」：小規模で生命表が作成されていない
                    life[cur] = None

    # 住基人口（男女別・5歳階級）
    jk = pd.read_excel(d / "2404ssnen.xlsx", header=None, skiprows=3, dtype=str)
    jk = jk[jk[0].str.fullmatch(r"\d{6}", na=False)]
    jk["code"] = jk[0].str[:5]
    ages = ["0", "5", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55", "60", "65", "70", "75", "80", "85", "90", "95", "100"]
    pop = {}
    for _, r in jk.iterrows():
        pop[(r["code"], r[3])] = dict(zip(ages, num(pd.Series(r[5:26].values)).tolist()))

    # 介護：保険者名 → 市区町村コード（都道府県名＋市区町村名で照合）
    name2code = {(p, n): c for c, p, n in zip(base.index, base["都道府県"], base["市区町村"])}
    age_blocks = {"65": 18, "70": 26, "75": 34, "80": 42, "85": 50, "90": 58, "2号": 66}  # 各ブロック先頭（要支援1）
    for sex, fname in (("男", "2406-h2-2.xlsx"), ("女", "2406-h2-3.xlsx")):
        kg = pd.read_excel(d / fname, header=None, skiprows=7)
        res = {}
        for _, r in kg.iterrows():
            code = name2code.get((r[0], r[1]))
            if code is None or life.get(code) is None or (code, sex) not in pop:
                continue
            p = pop[(code, sex)]
            # 要介護2〜5 は各ブロックの4〜7列目（先頭からのオフセット3〜6）
            care = {k: sum(float(r[s + o]) for o in range(3, 7)) for k, s in age_blocks.items()}
            rate = {}
            for k in ["65", "70", "75", "80", "85"]:
                rate[k] = care[k] / p[k] if p[k] else np.nan
            p90 = p["90"] + p["95"] + p["100"]
            rate["90"] = rate["95"] = care["90"] / p90 if p90 else np.nan
            p40 = sum(p[a] for a in ["40", "45", "50", "55", "60"])
            for a in ["40", "45", "50", "55", "60"]:
                rate[a] = care["2号"] / p40 if p40 else np.nan
            lx0 = life[code][sex][0][1]
            hl = 0.0
            for age_label, _, nLx in life[code][sex]:
                start = re.match(r"\s*(\d+)", age_label).group(1)
                start = "0" if start in ("0", "1") else start
                hl += nLx * (1 - min(rate.get(start, 0.0), 1.0))
            res[code] = hl / lx0
        col = f"健康寿命_{sex}性_近似"
        base[col] = pd.Series(res)
        define(col, "健康状態", "06_健康寿命",
               "サリバン法の近似：生命表(2020)の nLx ×（1 − 要介護2以上の割合(2024/6 ÷ 住基人口2024/1)）の合計 ÷ l0（歳）。広域連合加入の市町村は欠損",
               "2020/2024")


# ---------------------------------------------------------------- 07 自殺の基礎資料
def jisatsu(base):
    # zip は 07_自殺の基礎資料.py が R5_自殺日集計/ に展開済み
    path = next((RAW / "07_自殺の基礎資料" / "R5_自殺日集計").glob("*A7表*"))
    df = pd.read_excel(path, sheet_name=0, header=None, skiprows=8, dtype=str)
    df = df[df[1].str.fullmatch(r"\d{5,6}", na=False)]
    s = num(df.set_index(df[1].str.zfill(6).str[:5])[4])
    s = s[~s.index.duplicated()]
    cnt = s.reindex(base.index).fillna(0)  # 表に載っていない＝自殺者0人
    base["人口あたり自殺者数"] = cnt / base["人口"] * 1e5
    define("人口あたり自殺者数", "地域とのつながり", "07_自殺の基礎資料",
           "自殺者数（A7表 住居地・総数。掲載なしは0人）÷ 人口 ×10万（人/10万人）", "2023")


# ---------------------------------------------------------------- 08 住民基本台帳人口移動報告
def jinko_ido(base):
    df = pd.read_excel(RAW / "08_住民基本台帳人口移動報告" / "b01103s_表11-3_転入超過数_2024.xlsx",
                       header=None, skiprows=6, dtype=str)
    df = df[df[2] == "移動者"]
    s = num(df.set_index(df[5].str.zfill(5))[7])
    s = s[~s.index.duplicated()]
    # 東京23区は区ごと、政令市は市全体の行がある
    base["転入超過割合"] = s / base["人口"] * 100
    define("転入超過割合", "自己効力感", "08_住民基本台帳人口移動報告", "転入超過数（国内移動・移動者計）÷ 人口 ×100（%）", "2024")


# ---------------------------------------------------------------- 09 経済センサス2021
def keizai_census(base):
    raw = pd.read_excel(RAW / "09_経済センサス2021" / "b1_009_1a.xlsx", header=None, dtype=str)
    col = raw.columns[raw.iloc[5] == "94_宗教"][0]
    df = raw.iloc[9:]
    s = num(df.set_index(df[1].str[:5])[col])
    s = s[~s.index.duplicated()]
    base["人口あたり宗教の事業所数"] = s / base["人口"] * 1e5
    define("人口あたり宗教の事業所数", "地域とのつながり", "09_経済センサス2021", "産業中分類「94_宗教」の全事業所数 ÷ 人口 ×10万（所/10万人）", "2021")


# ---------------------------------------------------------------- 10 NPO法人
def npo(base):
    z = zipfile.ZipFile(RAW / "10_NPO法人" / "gyousei_000.zip")
    name = [n for n in z.namelist() if n.endswith(".csv")][0]
    df = pd.read_csv(z.open(name), encoding="cp932", dtype=str)
    df = df[df["解散情報"].isna() & df["主たる事務所の所在地"].notna()]

    city2pref = {"札幌市": "北海道", "仙台市": "宮城県", "さいたま市": "埼玉県", "千葉市": "千葉県", "横浜市": "神奈川県",
                 "川崎市": "神奈川県", "相模原市": "神奈川県", "新潟市": "新潟県", "静岡市": "静岡県", "浜松市": "静岡県",
                 "名古屋市": "愛知県", "京都市": "京都府", "大阪市": "大阪府", "堺市": "大阪府", "神戸市": "兵庫県",
                 "岡山市": "岡山県", "広島市": "広島県", "北九州市": "福岡県", "福岡市": "福岡県", "熊本市": "熊本県"}
    names = {p: sorted(((n, c) for c, pp, n in zip(base.index, base["都道府県"], base["市区町村"]) if pp == p),
                       key=lambda x: -len(x[0])) for p in PREFS}

    def locate(row):
        pref = city2pref.get(row["所轄庁"], row["所轄庁"])
        addr = str(row["主たる事務所の所在地"]).replace(" ", "").replace("　", "")
        if addr.startswith(pref):
            addr = addr[len(pref):]
        addr = re.sub(r"^.{1,4}?郡", "", addr)
        for n, c in names.get(pref, []):
            if addr.startswith(n):
                return c
        return None

    df["code"] = df.apply(locate, axis=1)
    cnt = df["code"].value_counts()
    base["人口あたりNPOの数"] = cnt.reindex(base.index).fillna(0) / base["人口"] * 1e5
    define("人口あたりNPOの数", "地域とのつながり", "10_NPO法人",
           f"現存法人（解散情報なし）を主たる事務所の所在地で市区町村に割当てて数える ÷ 人口 ×10万（法人/10万人）。割当不能 {df['code'].isna().sum()} 件",
           "2026/10/4時点")


# ---------------------------------------------------------------- 11 ウォーカブル推進都市
def walkable(base):
    pdf = next((RAW / "11_ウォーカブル推進都市").glob("*.pdf"))
    words = pymupdf.open(pdf)[0].get_text("words")
    # 多段組の一覧：列（幅約50pt）ごとに上から読む。都道府県見出しで現在の県を切り替える
    y_start = min(y0 for x0, y0, x1, y1, w, *_ in words if w == "北海道")  # 一覧の1行目（北海道の見出し）から下
    cells = {}
    for x0, y0, x1, y1, w, *_ in words:
        if y0 < y_start - 1 or "合計" in w:
            continue
        key = (int(((x0 + x1) / 2 - 10) // 50), round(y0))
        cells[key] = cells.get(key, "") + w
    cur, flags, unmatched = None, set(), []
    lookup = {(p, n): c for c, p, n in zip(base.index, base["都道府県"], base["市区町村"])}
    for (_, _), text in sorted(cells.items()):
        text = text.replace(" ", "")
        # 都道府県見出し（抽出すると「神神奈川県」のように先頭が重なる）と都道府県自体の参加（「神奈川県」）は、
        # どちらも現在の県を切り替える
        pref = next((p for p in PREFS if text.endswith(p) and p.startswith(text[:-len(p)])), None)
        if pref:
            cur = pref
        elif (cur, text) in lookup:
            flags.add(lookup[(cur, text)])
        else:
            unmatched.append(text)
    if unmatched:
        print("  ウォーカブル：照合できなかった名称", unmatched)
    base["ウォーカブル推進都市"] = base.index.isin(flags).astype(int)
    define("ウォーカブル推進都市", "公共空間", "11_ウォーカブル推進都市", f"推進都市一覧に掲載＝1（照合できた市区町村 {len(flags)}）", "2026/8/31時点")


# ---------------------------------------------------------------- 12 公共施設状況調
def koen(base):
    df = pd.read_excel(RAW / "12_公共施設状況調" / "市町村経年比較表_H18-R06_001068878.xlsx",
                       sheet_name="AFAHO14H1030", header=None, skiprows=7, dtype=str)
    df = df[(df[0].str.strip() == "2022") & df[2].str.fullmatch(r"\d{6}", na=False)]
    area = sum(num(df[c].replace("-", "0")).fillna(0) for c in (12, 14, 20, 22))
    s = pd.Series(area.values, index=df[2].str[:5].values)
    s = s[~s.index.duplicated()]
    base["人口あたり公園面積"] = s / base["人口"]
    define("人口あたり公園面積", "公共空間", "12_公共施設状況調",
           "公園面積の合計（都市計画区域内：市町村立計＋市町村立以外、区域外：市町村立計＋市町村立以外）÷ 人口（m²/人）", "2022年度")


def main():
    base = base_and_census()
    for step in (toshi_monitoring, shakai_jinko, jutaku, chiho_zaisei, kenko_jumyo,
                 jisatsu, jinko_ido, keizai_census, npo, walkable, koen):
        step(base)
        print(f"done: {step.__name__}")

    OUT.mkdir(parents=True, exist_ok=True)
    base.round(4).to_csv(OUT / "01_市区町村別_個別KPI.csv", encoding="utf-8-sig")
    defs = pd.DataFrame([(c, *DEFS[c], base[c].notna().sum()) for c in base.columns if c in DEFS],
                        columns=["列名", "分野", "出典フォルダ", "計算式・単位", "データ年", "値がある市区町村数"])
    defs.to_csv(OUT / "01_市区町村別_個別KPI_定義.csv", index=False, encoding="utf-8-sig")
    print(base.shape)
    print(defs[["列名", "値がある市区町村数"]].to_string(index=False))


if __name__ == "__main__":
    main()
