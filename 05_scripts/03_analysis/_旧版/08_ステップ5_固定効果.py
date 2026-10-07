"""ステップ5：年ごとの変化で確かめる（固定効果モデル）。年度ごとに値がある個別KPIを使う。

① その分野の実感 = β1·X ＋ 地域×年代×性別の効果 ＋ 年度の効果
② 幸福度        = β2·X ＋ 同上
X は年度ごとに値がある個別KPI（年度版Yの調査に、Y−1年の値を対応させる）を1本ずつ入れる。
係数は「市町村間の標準偏差1つ分」あたりにそろえ、市町村どうしの比較（改善候補②）の係数と並べて読めるようにする。
データ：年代×性別の行・2023〜26年度版、回答者数で重みづけ、標準誤差は地域ごとにまとめて計算（クラスタ）。
感度分析：回答者数5・10・20人以上。
出力：08_固定効果_係数.csv、08_個別KPIの年度変動.csv
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

from common import KPIS, TIME_VARYING, load_kpi, load_panel, load_rows, save

XS = [c for c in KPIS if c in TIME_VARYING]
rows = load_rows()
panel = load_panel()
d0 = rows.merge(panel, left_on=["市区町村コード", "年度"], right_on=["市区町村コード", "年度版"], how="left")
d0["cell"] = d0["地域ID"].astype(str) + "_" + d0["年代"] + "_" + d0["性別"]
kpi = load_kpi().set_index("市区町村コード").loc[rows["市区町村コード"].unique()]
cross_sd = kpi[XS].std()  # 分析対象680市町村の、市町村間の標準偏差


def within(df, cols, w):
    return pd.DataFrame({c: df[c] - (df[c] * w).groupby(df["cell"]).transform("sum") / w.groupby(df["cell"]).transform("sum")
                         for c in cols})


out = []
for th in [5, 10, 20]:
    d = d0[d0["回答者数"] >= th].copy()
    for yr in (2024, 2025, 2026):
        d[f"y{yr}"] = (d["年度"] == yr).astype(float)
    for x in XS:
        field, sign, label = KPIS[x]
        sub = d[d[x].notna()].copy()
        sub["X"] = sub[x] / cross_sd[x]
        w = sub["回答者数"].astype(float)
        for yname, ycol in [("幸福度", "幸福度"), ("実感", f"主観_{field}")]:
            cols = [ycol, "X", "y2024", "y2025", "y2026"]
            dm = within(sub, cols, w)
            fit = sm.WLS(dm[ycol], dm[["X", "y2024", "y2025", "y2026"]], weights=w).fit(
                cov_type="cluster", cov_kwds={"groups": sub["地域ID"]})
            b, se, p = fit.params["X"], fit.bse["X"], fit.pvalues["X"]
            out.append((f"{th}人以上", len(sub), sub["地域ID"].nunique(), label, x, field, sign, yname,
                        b, b - 1.96 * se, b + 1.96 * se, p))
res = pd.DataFrame(out, columns=["条件", "行", "地域", "個別KPI", "列名", "分野", "望ましい向き", "目的変数",
                                 "係数_1SD", "下限95", "上限95", "p値"])
res["q値"] = res.groupby("条件")["p値"].transform(lambda s: multipletests(s, method="fdr_bh")[1])
res["想定どおり有意"] = (res["p値"] < 0.05) & (np.sign(res["係数_1SD"]) == res["望ましい向き"])
res["逆向きに有意"] = (res["p値"] < 0.05) & (np.sign(res["係数_1SD"]) == -res["望ましい向き"])
save(res, "08_固定効果_係数.csv")

# 年度で動く大きさ：市町村の中での年度変化の標準偏差 ÷ 市町村間の標準偏差（680市町村、年度版2023〜26）
p = panel[panel["市区町村コード"].isin(kpi.index) & panel["年度版"].between(2023, 2026)]
var = []
for x in XS:
    wsd = (p[x] - p.groupby("市区町村コード")[x].transform("mean")).std()
    var.append((KPIS[x][2], x, wsd / cross_sd[x]))
save(pd.DataFrame(var, columns=["個別KPI", "列名", "年度変化の大きさ（市町村間の差に対する比）"]), "08_個別KPIの年度変動.csv")

main = res[res["条件"] == "5人以上"]
print(main.pivot_table(index="個別KPI", columns="目的変数", values=["係数_1SD", "p値"]).round(3).to_string())
print(pd.DataFrame(var).round(2).to_string())
