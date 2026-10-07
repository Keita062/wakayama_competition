"""市区町村 × 性別 × 年代（10歳階級）の人口を縦持ちの1枚の表にまとめる。

入力 : 04_data/01_raw/15_年齢別人口/b02_07.xlsx（05_scripts/01_download/15_年齢別人口.py で取得）
       令和2年国勢調査 人口等基本集計 第2-7表 男女，年齢（5歳階級）別人口（国籍総数）
出力 : 04_data/02_processed/04_年齢別人口.csv
       列：市区町村コード, 都道府県, 市区町村, 性別, 年代, 人口

行   : 全国の市区町村（政令市は市全体の1行、東京23区は区ごと。政令市の区は含めない）
       × 性別2（男性・女性）× 年代8（10代〜80代以上）
キー : 5桁の市区町村コード（令和2年国勢調査の地域コード。01_市区町村別_個別KPI.csv と同じ選び方）
年代 : 10代 = 15〜19歳のみ（0〜14歳は含めない）、20代 = 20〜24歳 + 25〜29歳 … 70代、
       80代以上 = 80〜84歳 + 85〜89歳 + 90〜94歳 + 95〜99歳 + 100歳以上
       年齢「不詳」は按分せず含めない（そのため 15歳以上の合計 = 総数 − 15歳未満 − 年齢不詳）。
調査時点: 2020年10月1日
"""
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
RAW = BASE / "04_data" / "01_raw" / "15_年齢別人口"
OUT = BASE / "04_data" / "02_processed"

AGE_GROUPS = {
    "10代": ["04_15～19歳"],
    "20代": ["05_20～24歳", "06_25～29歳"],
    "30代": ["07_30～34歳", "08_35～39歳"],
    "40代": ["09_40～44歳", "10_45～49歳"],
    "50代": ["11_50～54歳", "12_55～59歳"],
    "60代": ["13_60～64歳", "14_65～69歳"],
    "70代": ["15_70～74歳", "16_75～79歳"],
    "80代以上": ["17_80～84歳", "18_85～89歳", "19_90～94歳", "20_95～99歳", "21_100歳以上"],
}
SEX = {"1_男": "男性", "2_女": "女性"}


def num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def read_b02_07() -> pd.DataFrame:
    """id列は12行目（0始まり11行目）、年齢の列は10行目（同9行目）の見出しで名前を付ける。"""
    raw = pd.read_excel(RAW / "b02_07.xlsx", header=None, dtype=str)
    ids, labels = raw.iloc[11].tolist(), raw.iloc[9].tolist()
    cols = [l if isinstance(l, str) and l.strip() else ids[i] for i, l in enumerate(labels)]
    df = raw.iloc[12:].copy()
    df.columns = cols
    df = df[~df["地域名"].astype(str).str.contains("旧：")]
    df["code"] = df["2020年_地域コード"].str[:5]
    return df


def main() -> None:
    df = read_b02_07()
    df = df[(df["国籍総数か日本人"] == "0_国籍総数") & df["男女"].isin(SEX)]
    # 01_市区町村別KPI表の作成.py と同じ選び方：政令市(1)・市(2)・町村(3)＋東京23区(0, 131xx)。特別区部(13100)は除く
    kind = df["地域識別コード"]
    is_ku23 = (kind == "0") & df["code"].str.startswith("131")
    df = df[kind.isin(["1", "2", "3"]) & (df["code"] != "13100") | is_ku23]

    rows = []
    for age, cols in AGE_GROUPS.items():
        rows.append(pd.DataFrame({
            "市区町村コード": df["code"].values,
            "都道府県": df["2020年_都道府県"].str.split("_").str[1].values,
            "市区町村": df["地域名"].str.split("_", n=1).str[1].values,
            "性別": df["男女"].map(SEX).values,
            "年代": age,
            "人口": df[cols].apply(num).sum(axis=1).astype(int).values,
        }))
    out = pd.concat(rows, ignore_index=True)
    out["性別"] = pd.Categorical(out["性別"], ["男性", "女性"])
    out["年代"] = pd.Categorical(out["年代"], list(AGE_GROUPS))
    out = out.sort_values(["市区町村コード", "性別", "年代"]).reset_index(drop=True)

    # 検算：15歳以上の合計 = 総数 − 15歳未満 − 年齢不詳（男女・市区町村ごと、全件）
    chk = df.set_index(["code", df["男女"].map(SEX)])
    expected = num(chk["00_総数"]) - num(chk["R1_（再掲）15歳未満"]) - num(chk["22_年齢「不詳」"])
    got = out.groupby(["市区町村コード", "性別"], observed=True)["人口"].sum()
    diff = (got - expected.reindex(got.index)).abs()
    assert diff.max() == 0, diff[diff > 0]

    OUT.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT / "04_年齢別人口.csv", index=False, encoding="utf-8-sig")
    print(f"saved 04_年齢別人口.csv: {len(out):,} 行, {out['市区町村コード'].nunique():,} 市区町村")


if __name__ == "__main__":
    main()
