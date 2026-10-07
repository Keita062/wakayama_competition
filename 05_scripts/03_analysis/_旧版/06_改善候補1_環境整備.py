"""改善候補①：環境整備で実感が上がる分野かを分ける。

市町村ごとの実感（年代×性別の構成をそろえた主観、ステップ2で作成）を、
「類型だけ」と「類型＋その分野の個別KPI（標準化）」で説明したときの交差検証R²（10分割×乱数5通りの平均）を比べる。
- 上乗せ（個別KPIによるR²の増分）が10ポイント以上 →「環境整備で上がる」
- 類型＋個別KPIの重回帰で、想定どおりの向きで有意（5%水準）な個別KPI →「効いた」
個別KPIが欠けている市町村は、その分野の計算から除く。
出力：06_交差検証R2.csv、06_個別KPIの係数.csv、06_実感の予測と実績.csv（和歌山・田辺の予測との差）
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold, cross_val_predict

from common import KPI_FIELDS, KPIS, OUT, load_kpi, pct_rank, save

v = pd.read_csv(OUT / "03_市町村別_主観.csv", dtype={"市区町村コード": str}).set_index("市区町村コード")
kpi = load_kpi().set_index("市区町村コード").loc[v.index]
T = pd.get_dummies(v["類型"], drop_first=True).astype(float)
lmg = pd.read_csv(OUT / "04_寄与度.csv")
lmg = lmg[lmg["対象"] == "類型を揃えた全国"].set_index("分野")["取り分%"]


def cv_r2(X, y, seeds=range(5)):
    r = []
    for s in seeds:
        p = cross_val_predict(LinearRegression(), X, y, cv=KFold(10, shuffle=True, random_state=s))
        r.append(1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum())
    return float(np.mean(r))


r2_rows, coef_rows, pred_rows = [], [], []
for f in KPI_FIELDS:
    cols = [c for c, (ff, _, _) in KPIS.items() if ff == f]
    y = v[f"主観_{f}"]
    ok = kpi[cols].notna().all(axis=1)
    yy, TT, K = y[ok], T[ok], kpi.loc[ok, cols]
    Kz = (K - K.mean()) / K.std()
    r_type = cv_r2(TT.values, yy.values)
    r_full = cv_r2(np.hstack([TT.values, Kz.values]), yy.values) if cols else r_type
    lift = (r_full - r_type) * 100
    effective = []
    if cols:
        fit = sm.OLS(yy, sm.add_constant(pd.concat([TT, Kz], axis=1))).fit()
        for c in cols:
            sign = KPIS[c][1]
            sig = fit.pvalues[c] < 0.05 and np.sign(fit.params[c]) == sign
            coef_rows.append((f, KPIS[c][2], sign, fit.params[c], fit.pvalues[c], sig))
            if sig:
                effective.append(KPIS[c][2])
        resid = yy - fit.fittedvalues
        pr = pct_rank(resid)
        for code in yy.index:
            pred_rows.append((f, code, yy[code], fit.fittedvalues[code], resid[code], pr[code]))
    judge = "環境整備で上がる" if lift >= 10 else "上がらない"
    if f == "地域とのつながり" and lift >= 10:
        judge = "一部は上がる"  # 効いたKPIのうち施策で動かせるのはNPOと高齢単身世帯への対応だけ（PDFの判断）
    r2_rows.append((f, lmg.get(f, np.nan), ok.sum(), r_type * 100, r_full * 100, lift, judge, "・".join(effective) or "なし"))

r2 = pd.DataFrame(r2_rows, columns=["分野", "幸福度への寄与%", "市町村数", "類型だけ%", "類型＋個別KPI%", "上乗せ", "判定", "効いた個別KPI"])
r2 = r2.sort_values("上乗せ", ascending=False)
save(r2, "06_交差検証R2.csv")
save(pd.DataFrame(coef_rows, columns=["分野", "個別KPI", "望ましい向き", "係数_1SD", "p値", "効いた"]), "06_個別KPIの係数.csv")
pred = pd.DataFrame(pred_rows, columns=["分野", "市区町村コード", "実感", "予測", "予測との差", "予測との差_全国パーセンタイル"])
pred = pred.join(v[["都道府県", "市区町村", "類型"]], on="市区町村コード")
save(pred, "06_実感の予測と実績.csv")
print(r2.round(0).to_string(index=False))
