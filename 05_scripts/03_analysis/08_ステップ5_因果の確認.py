"""ステップ5：因果の確認 ― 同じ地域の中で変数が年ごとに変わったとき、重点分野の主観スコアと幸福度も変わったかを確かめる（固定効果モデル）。

対象：重点分野（ステップ4）の変数（個別KPI・追加の変数）のうち、年度ごとに値があるもの。1時点しかない変数は確かめられない。
モデル（変数を1本ずつ入れる）：
  ① 重点分野の主観スコア = β·X ＋ 地域×年代×性別の効果 ＋ 年度の効果
  ② 幸福度             = β·X ＋ 同上
  地域ごとの変わらない特徴（都市規模、地域の気風など、測っていないものも含む）と全国共通の年度の変化を取り除き、
  同じ地域・同じ年代×性別の中でXが年ごとに変わった分だけでβを推定する。市町村どうしの比較（改善候補①②）で
  残りうる「測っていない違い」の影響を受けないため、因果に近い確かめ方になる。
データ：年代×性別の行（回答者5人以上）・年度版2023〜26。Xは年度版Yの調査にY−1年の値を対応させる。回答者数で重みづけ。
  標準誤差は地域ごとにまとめて計算（クラスタ）。係数は市町村どうしの標準偏差1つ分あたりにそろえる。
  複数の変数を調べるので、目的変数ごとに偽発見率（Benjamini–Hochberg）で補正したq値も出す。
出力：08_因果_係数.csv、08_年度変動.csv
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

from common import KPIS, PROCESSED, TIME_VARYING, load_focus, load_panel, load_rows, save

focus = load_focus()
defs = pd.read_csv(PROCESSED / "03_追加変数_定義.csv").set_index("列名")
extra = pd.read_csv(PROCESSED / "03_追加変数.csv", dtype={"市区町村コード": str})
panel = load_panel()
rows = load_rows()
codes = rows["市区町村コード"].unique()

# 重点分野の、年度ごとに値がある変数：列名 → (分野, 望ましい向き, 表示名, 年度ごとの表)
XS = {}
for field in dict.fromkeys(focus.values()):
    for c, (f, sign, label) in KPIS.items():
        if f == field and c in TIME_VARYING:
            XS[c] = (field, sign, label, panel[["市区町村コード", "年度版", c]])
    for c in defs.index[(defs["分野"] == field) & (defs["年ごとの値の有無"] == "あり")]:
        XS[c] = (field, int(defs.loc[c, "望ましい向き"]), defs.loc[c, "表示名"], extra[["市区町村コード", "年度版", c]])

rows["cell"] = rows["地域ID"].astype(str) + "_" + rows["年代"] + "_" + rows["性別"]
for yr in (2024, 2025, 2026):
    rows[f"y{yr}"] = (rows["年度"] == yr).astype(float)


def within(df, cols, w):
    """地域×年代×性別ごとの重みつき平均を引く（固定効果を取り除く）。"""
    return pd.DataFrame({c: df[c] - (df[c] * w).groupby(df["cell"]).transform("sum") / w.groupby(df["cell"]).transform("sum")
                         for c in cols})


out, var = [], []
for x, (field, sign, label, tbl) in XS.items():
    t = tbl[tbl["市区町村コード"].isin(codes) & tbl["年度版"].between(2023, 2026)]
    cross_sd = t.groupby("市区町村コード")[x].mean().std()  # 市町村どうしの標準偏差
    within_sd = (t[x] - t.groupby("市区町村コード")[x].transform("mean")).std()  # 市町村の中での年ごとの変化
    var.append((field, label, x, within_sd / cross_sd))
    d = rows.merge(t.rename(columns={"年度版": "年度"}), on=["市区町村コード", "年度"], how="inner").dropna(subset=[x])
    d["X"] = d[x] / cross_sd
    w = d["回答者数"].astype(float)
    for yname, ycol in [("重点分野の主観スコア", f"主観_{field}"), ("幸福度", "幸福度")]:
        cols = [ycol, "X", "y2024", "y2025", "y2026"]
        dm = within(d, cols, w)
        fit = sm.WLS(dm[ycol], dm[["X", "y2024", "y2025", "y2026"]], weights=w).fit(
            cov_type="cluster", cov_kwds={"groups": d["地域ID"]})
        b, se, p = fit.params["X"], fit.bse["X"], fit.pvalues["X"]
        out.append((field, label, x, sign, yname, len(d), d["地域ID"].nunique(), b, b - 1.96 * se, b + 1.96 * se, p))
res = pd.DataFrame(out, columns=["分野", "表示名", "列名", "望ましい向き", "目的変数", "行", "地域", "係数_1SD", "下限95", "上限95", "p値"])
res["q値"] = res.groupby("目的変数")["p値"].transform(lambda s: multipletests(s, method="fdr_bh")[1])
res["想定どおり有意"] = (res["p値"] < 0.05) & (np.sign(res["係数_1SD"]) == res["望ましい向き"])
res["逆向きに有意"] = (res["p値"] < 0.05) & (np.sign(res["係数_1SD"]) == -res["望ましい向き"])
save(res, "08_因果_係数.csv")
save(pd.DataFrame(var, columns=["分野", "表示名", "列名", "年度変化の大きさ（市町村どうしの差に対する比）"]), "08_年度変動.csv")
print(res.round(3).to_string(index=False))
print(pd.DataFrame(var).round(3).to_string(index=False))
