"""性別×年代の分析の共通処理：区分の定義、区分ごとの行の読み込み、市×区分の値の縮小推定、人口。

区分：性別（女性・男性）×年代（20〜30代・40代・50代・60代・70代以上）の10区分。
  20代と80代以上は全国でも行が少ない（20代男性132行・80代以上女性55行）ため、隣の年代とまとめる。10代（3行）は使わない。
結果は 04_data/04_segment/ に、レポートは 01_docs/04_和歌山_性別×年代分析.md に出す。
既存の分析（05_scripts/03_analysis/）の common.py・explain.py をそのまま使う。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03_analysis"))
from common import BASE, OUT, PROCESSED, load_rows, wmean  # noqa: E402

SEG_OUT = BASE / "04_data" / "04_segment"
SEG_OUT.mkdir(parents=True, exist_ok=True)
AGE_BAND = {"20代": "20〜30代", "30代": "20〜30代", "40代": "40代", "50代": "50代", "60代": "60代", "70代": "70代以上", "80代以上": "70代以上"}
AGES = ["20〜30代", "40代", "50代", "60代", "70代以上"]
SEXES = ["女性", "男性"]
SEGS = [f"{s}・{a}" for s in SEXES for a in AGES]
KEYS = ["類型", "年度", "年代", "性別"]  # 比べる土台（元の10歳階級の年代のまま、同じ類型・年度・年代・性別の平均を引く）


def load_seg_rows():
    """分析対象行（年代×性別、回答者5人以上）に区分を付ける。10代は除く。"""
    rows = load_rows()
    rows["年代区分"] = rows["年代"].map(AGE_BAND)
    rows = rows.dropna(subset=["年代区分"]).reset_index(drop=True)
    rows["区分"] = rows["性別"] + "・" + rows["年代区分"]
    return rows


def resid(rows, cols, keys=KEYS):
    """各行から、同じ keys の平均（回答者数で重みづけ）を引く。"""
    out = rows.copy()
    w = rows["回答者数"].astype(float)

    for c in cols:
        m = (rows[c] * w).groupby([rows[k] for k in keys]).transform("sum") / w.groupby([rows[k] for k in keys]).transform("sum")
        out[c] = rows[c] - m
    return out


def shrink(r, col):
    """市×区分の値（行の残差を回答者数で重みづけした平均）を、経験ベイズで0（同じ類型・同じ区分の平均）に向けて縮める。

    行の残差の2乗の期待値 ＝ τ² ＋ σ²／回答者数（τ²：市町村どうしの本当の差の分散、σ²：1人ひとりのばらつき）とみなし、
    区分ごとに 残差² を 1／回答者数 に回帰して τ²・σ² を出す。市×区分の値 m（回答者数の合計 N）は
    B＝τ²／(τ²＋σ²／N) をかけて縮め（回答者が少ないほど0に近づく）、不確かさは √(B·σ²／N)。
    戻り値：市区町村コード×区分ごとの 生の値・回答者数・縮めた値・標準誤差・B。
    """
    out = []
    for seg, d in r.groupby("区分"):
        n = d["回答者数"].values.astype(float)
        e2 = d[col].values ** 2
        X = np.column_stack([np.ones(len(d)), 1 / n])
        beta = np.linalg.lstsq(X * np.sqrt(n)[:, None], e2 * np.sqrt(n), rcond=None)[0]
        tau2, sig2 = max(beta[0], 1e-6), max(beta[1], 1e-6)
        g = d.assign(wv=d[col] * n).groupby("市区町村コード").agg(和=("wv", "sum"), 回答者数=("回答者数", "sum"))
        m = g["和"] / g["回答者数"]
        B = tau2 / (tau2 + sig2 / g["回答者数"])
        out.append(pd.DataFrame({"区分": seg, "生の値": m, "回答者数": g["回答者数"], "縮めた値": B * m,
                                 "標準誤差": np.sqrt(B * sig2 / g["回答者数"]), "B": B}))
    return pd.concat(out).reset_index()


def load_pop():
    """市区町村×区分の人口（国勢調査2020。05_scripts/02_build/04_年齢別人口の作成.py）。"""
    p = pd.read_csv(PROCESSED / "04_年齢別人口.csv", dtype={"市区町村コード": str})
    p["年代区分"] = p["年代"].map(AGE_BAND)
    p = p.dropna(subset=["年代区分"])
    p["区分"] = p["性別"] + "・" + p["年代区分"]
    return p.groupby(["市区町村コード", "区分"])["人口"].sum().rename("人口").reset_index()


def save(df, name, index=False):
    df.to_csv(SEG_OUT / name, index=index, encoding="utf-8-sig")
    return SEG_OUT / name


def wakayama6():
    return pd.read_csv(OUT / "03_6市の判定.csv")


def targets():
    """ステップ2で決めたターゲットの市（市名 → 類型）。"""
    j = wakayama6()
    j = j[j["判定"].str.contains("ターゲット")]
    return j.set_index("市")["類型"].to_dict()


EXTRA_FILES = ["03_追加変数", "05_追加変数_住宅環境", "06_追加変数_健康状態"]


def load_extra():
    """追加の変数（あるファイルだけ）を1つの表にまとめる。戻り値：値の表（市区町村コード×年度版）、定義の表（列名が索引）。
    定義に「操作可能性」の列がないファイル（03_追加変数）は common.CONTROL を使う。"""
    from common import CONTROL
    vals, defs = None, []
    for name in EXTRA_FILES:
        f = PROCESSED / f"{name}.csv"
        if not f.exists():
            continue
        v = pd.read_csv(f, dtype={"市区町村コード": str})
        vals = v if vals is None else vals.merge(v, on=["市区町村コード", "年度版"], how="outer")
        defs.append(pd.read_csv(PROCESSED / f"{name}_定義.csv"))
    d = pd.concat(defs).drop_duplicates("列名").set_index("列名")
    for k in ["操作可能性", "操作可能性の理由"]:
        if k in d:
            d[k] = d[k].astype(object)
    if "操作可能性" not in d:
        d["操作可能性"] = pd.Series(np.nan, index=d.index, dtype=object)
        d["操作可能性の理由"] = pd.Series(np.nan, index=d.index, dtype=object)
    for c in d.index:
        if pd.isna(d.loc[c, "操作可能性"]) and c in CONTROL:
            d.loc[c, ["操作可能性", "操作可能性の理由"]] = CONTROL[c]
    return vals, d
