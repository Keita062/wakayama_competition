"""改善候補②：幸福度や実感と結びつき、ターゲットの市が同じ類型の中で見劣りしている個別KPIを挙げる。

1. 類型を固定し、個別KPIが1標準偏差違うと幸福度（年代×性別の構成をそろえた値）が何点違うかを、KPIを1本ずつ調べる
   （市町村の回答者数で重みづけした回帰）。
   想定どおりの向きで有意（5%水準）なら「幸福度と結びつく」。
2. 個別KPIをまとめて類型に足したとき、幸福度の説明力（R²）がどこまで上がるかを見る（欠損は類型の中央値で補完）。
3. 和歌山市・田辺市の各KPIを同じ類型の中で順位づけ（望ましい向きにそろえ、小さいほど見劣り）し、20%以下を並べる。
   「幸福度の差の目安」＝係数（1SDあたり）×（類型の中央値 − 市の値）÷ SD を望ましい向きにそろえた値
出力：07_幸福度と個別KPI.csv、07_説明力.csv、07_市別の見劣りKPI.csv
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import KPIS, OUT, TYPE_VARS, load_kpi, load_rows, save

v = pd.read_csv(OUT / "03_市町村別_主観.csv", dtype={"市区町村コード": str}).set_index("市区町村コード")
kpi = load_kpi().set_index("市区町村コード").loc[v.index]
T = pd.get_dummies(v["類型"], drop_first=True).astype(float)
coef1 = pd.read_csv(OUT / "06_個別KPIの係数.csv")
jikkan = set(coef1.loc[coef1["効いた"], "個別KPI"])
y = v["幸福度"]
n_resp = load_rows().groupby("市区町村コード")["回答者数"].sum().loc[v.index]  # 回帰の重み

# 頑健性：類型に加えて、類型の6変数（人口・人口密度は対数）を連続値でもそろえる
C6 = kpi[TYPE_VARS].copy()
C6["人口"], C6["人口密度"] = np.log(C6["人口"]), np.log(C6["人口密度"])
C6 = (C6 - C6.mean()) / C6.std()

rows = []
for c, (field, sign, label) in KPIS.items():
    ok = kpi[c].notna()
    x = kpi.loc[ok, c]
    sd = x.std()
    z = ((x - x.mean()) / sd).rename("z")
    fit = sm.WLS(y[ok], sm.add_constant(pd.concat([T[ok], z], axis=1)), weights=n_resp[ok]).fit()
    b, p = fit.params["z"], fit.pvalues["z"]
    controls = C6.drop(columns=[c], errors="ignore")[ok]  # KPI自身が類型変数のときは外す
    fit2 = sm.WLS(y[ok], sm.add_constant(pd.concat([T[ok], controls, z], axis=1)), weights=n_resp[ok]).fit()
    b2, p2 = fit2.params["z"], fit2.pvalues["z"]
    rows.append((label, c, field, sign, b, p, p < 0.05 and np.sign(b) == sign, b2, p2, p2 < 0.05 and np.sign(b2) == sign,
                 label in jikkan, sd, ok.sum()))
hap = pd.DataFrame(rows, columns=["個別KPI", "列名", "分野", "望ましい向き", "係数_1SD", "p値", "幸福度と結びつく",
                                  "係数_1SD_頑健", "p値_頑健", "頑健でも結びつく", "実感と結びつく", "SD", "市町村数"])
hap = hap.sort_values("係数_1SD", key=abs, ascending=False)
save(hap, "07_幸福度と個別KPI.csv")

# 説明力：類型だけ → 類型＋個別KPIすべて
K = kpi[list(KPIS)]
K = K.fillna(K.groupby(v["類型"]).transform("median"))
Kz = (K - K.mean()) / K.std()
r_type = sm.WLS(y, sm.add_constant(T), weights=n_resp).fit().rsquared
r_all = sm.WLS(y, sm.add_constant(pd.concat([T, Kz], axis=1)), weights=n_resp).fit().rsquared
save(pd.DataFrame([("類型だけ", r_type * 100), (f"類型＋個別KPI{len(KPIS)}本", r_all * 100)], columns=["モデル", "R2%"]), "07_説明力.csv")

# 市別の見劣りKPI
out = []
for city in ["和歌山市", "田辺市"]:
    code = v.index[(v["都道府県"] == "和歌山県") & (v["市区町村"] == city)][0]
    same = v.index[v["類型"] == v.loc[code, "類型"]]
    for _, h in hap.iterrows():
        c, sign = h["列名"], h["望ましい向き"]
        x = kpi.loc[same, c].dropna()
        if code not in x.index:
            continue
        pct = (sign * x).rank(method="max")[code] / len(x) * 100  # 小さいほど見劣り（その値以下の市町村の割合）
        med = x.median()
        gain = h["係数_1SD"] * (med - x[code]) / h["SD"]
        out.append((city, v.loc[code, "類型"], h["個別KPI"], h["分野"], x[code], med, pct,
                    h["実感と結びつく"], h["幸福度と結びつく"], gain if h["幸福度と結びつく"] else np.nan))
city = pd.DataFrame(out, columns=["市", "類型", "個別KPI", "分野", "市の値", "類型中央値", "類型内%", "実感", "幸福度", "幸福度の差の目安"])
city = city[city["類型内%"] <= 20].sort_values(["市", "類型内%"])
save(city, "07_市別の見劣りKPI.csv")
print(hap[["個別KPI", "係数_1SD", "p値", "係数_1SD_頑健", "p値_頑健", "実感と結びつく"]].round(3).to_string(index=False))
print("R2:", round(r_type * 100), "->", round(r_all * 100))
print(city.round(2).to_string(index=False))
