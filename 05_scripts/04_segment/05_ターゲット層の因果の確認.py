"""区分のステップ5：ターゲット層の行だけで、因果の確認（固定効果モデル）を行う。方法は既存の 08_ステップ5_因果の確認.py と同じ。

対象：ターゲット層の重点分野の変数のうち、年度ごとに値があるもの（個別KPI・追加の変数）。
モデル（変数を1本ずつ）：
  ① 重点分野の主観スコア = β·X ＋ 地域×年代×性別の効果 ＋ 年度の効果
  ② 幸福度             = β·X ＋ 同上
データ：全国の、ターゲット層の区分に入る行（回答者5人以上、年度版2023〜26）。回答者数で重みづけ、標準誤差は地域ごとのクラスタ。
係数は市町村どうしの標準偏差1つ分あたり。目的変数ごとに偽発見率（Benjamini–Hochberg）で補正したq値も出す。
出力：05_因果_係数.csv、05_年度変動.csv
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

from seg_common import SEG_OUT, load_extra, load_seg_rows, save
from common import KPIS, TIME_VARYING, load_panel

best = pd.read_csv(SEG_OUT / "03_ターゲット層.csv")
extra, defs = load_extra()
panel = load_panel()
rows = load_seg_rows()
codes = rows["市区町村コード"].unique()
rows["cell"] = rows["地域ID"].astype(str) + "_" + rows["年代"] + "_" + rows["性別"]
for yr in (2024, 2025, 2026):
    rows[f"y{yr}"] = (rows["年度"] == yr).astype(float)


def within(df, cols, w):
    return pd.DataFrame({c: df[c] - (df[c] * w).groupby(df["cell"]).transform("sum") / w.groupby(df["cell"]).transform("sum")
                         for c in cols})


out, var = [], []
for _, t in best.iterrows():
    field = t["分野"]
    parts = t["区分"].split("・")
    segs = [f"{a}・{b}" for a, b in zip(parts[0::2], parts[1::2])]
    rr = rows[rows["区分"].isin(segs)]
    xs = {}
    for c, (f, sign, label) in KPIS.items():
        if f == field and c in TIME_VARYING:
            xs[c] = (sign, label, panel[["市区町村コード", "年度版", c]])
    for c in defs.index[(defs["分野"] == field) & (defs["年ごとの値の有無"].astype(str).str.startswith("あり"))]:
        xs[c] = (int(defs.loc[c, "望ましい向き"]), defs.loc[c, "表示名"], extra[["市区町村コード", "年度版", c]])
    for x, (sign, label, tbl) in xs.items():
        tb = tbl[tbl["市区町村コード"].isin(codes) & tbl["年度版"].between(2023, 2026)].dropna(subset=[x])
        cross_sd = tb.groupby("市区町村コード")[x].mean().std()
        within_sd = (tb[x] - tb.groupby("市区町村コード")[x].transform("mean")).std()
        var.append((t["市"], field, t["層"], label, x, within_sd / cross_sd))
        d = rr.merge(tb.rename(columns={"年度版": "年度"}), on=["市区町村コード", "年度"], how="inner")
        d["X"] = d[x] / cross_sd
        w = d["回答者数"].astype(float)
        for yname, ycol in [("重点分野の主観スコア", f"主観_{field}"), ("幸福度", "幸福度")]:
            cols = [ycol, "X", "y2024", "y2025", "y2026"]
            dm = within(d, cols, w)
            fit = sm.WLS(dm[ycol], dm[["X", "y2024", "y2025", "y2026"]], weights=w).fit(cov_type="cluster", cov_kwds={"groups": d["地域ID"]})
            b, se, p = fit.params["X"], fit.bse["X"], fit.pvalues["X"]
            out.append((t["市"], field, t["層"], label, x, sign, yname, len(d), d["地域ID"].nunique(), b, b - 1.96 * se, b + 1.96 * se, p))
res = pd.DataFrame(out, columns=["市", "分野", "層", "表示名", "列名", "望ましい向き", "目的変数", "行", "地域", "係数_1SD", "下限95", "上限95", "p値"])
if len(res):
    res["q値"] = res.groupby(["市", "目的変数"])["p値"].transform(lambda s: multipletests(s, method="fdr_bh")[1])
    res["想定どおり有意"] = (res["p値"] < 0.05) & (np.sign(res["係数_1SD"]) == res["望ましい向き"])
    res["逆向きに有意"] = (res["p値"] < 0.05) & (np.sign(res["係数_1SD"]) == -res["望ましい向き"])
save(res, "05_因果_係数.csv")
save(pd.DataFrame(var, columns=["市", "分野", "層", "表示名", "列名", "年度変化の大きさ（市町村どうしの差に対する比）"]), "05_年度変動.csv")
print(res.round(3).to_string(index=False))
