"""改善候補①：主観の重点分野のスコアを、その分野の個別KPIで説明できるかを確かめる（Elastic Net回帰。方法は explain.py）。

対象：ステップ4で決めた重点分野（ターゲットの市ごとに1つ）。
比べる2つのモデル（どちらも市町村×年度版2023〜26、回答者数で重みづけ）：
  - 土台：類型（ダミー）＋類型の6変数（人口・人口密度は対数）＋年度（ダミー）
  - 土台＋その分野の個別KPI（年度ごとに値があるものは年度ごとの値）
個別KPIによる交差検証R²の上乗せの95%信頼区間（市町村単位のブートストラップ、explain.lift_test）の下限が0を超えれば
「個別KPIで説明できる」、超えなければ「個別KPIでは説明できない」。
出力：06_説明力.csv、06_個別KPIの係数.csv、06_主観スコアの予測と実績.csv
"""
import numpy as np
import pandas as pd

from common import CONTROL, KPIS, TIME_VARYING, TYPE_VARS, load_focus, save
from explain import build, fit, lift_test

focus = load_focus()
models, coefs, preds = [], [], []
for field in dict.fromkeys(focus.values()):
    cols = [c for c, (f, _, _) in KPIS.items() if f == field]
    d = build(field, cols).dropna(subset=["主観スコア"] + TYPE_VARS + cols).reset_index(drop=True)
    r0, _, _, p0 = fit(d, [], {})
    r1, en, coef, pred = fit(d, cols, {c: KPIS[c][1] for c in cols})
    lift, lo, hi, pv, r0, r1 = lift_test(d, p0, pred)
    models.append((field, "・".join(c for c, f in focus.items() if f == field), len(d), d["市区町村コード"].nunique(),
                   r0, r1, lift, lo, hi, pv, en.alpha_, en.l1_ratio_))
    coef.insert(0, "分野", field)
    coefs.append(coef)
    pred.insert(0, "分野", field)
    preds.append(pred)
m = pd.DataFrame(models, columns=["分野", "重点分野の市", "行数", "市町村数", "土台_交差検証R2%", "土台＋個別KPI_交差検証R2%", "上乗せ", "上乗せ_下限95", "上乗せ_上限95", "p値_片側", "alpha", "l1_ratio"])
m["判定"] = np.where(m["上乗せ_下限95"] > 0, "個別KPIで説明できる", "個別KPIでは説明できない")
c = pd.concat(coefs)
c["個別KPI"] = c["列名"].map(lambda x: KPIS[x][2])
c["操作可能性"] = c["列名"].map(lambda x: CONTROL[x][0])
c["操作可能性の理由"] = c["列名"].map(lambda x: CONTROL[x][1])
c["年度ごとの値"] = c["列名"].isin(TIME_VARYING)
save(m, "06_説明力.csv")
save(c, "06_個別KPIの係数.csv")
save(pd.concat(preds), "06_主観スコアの予測と実績.csv")
print(m.round(2).to_string(index=False))
print(c.round(3).to_string(index=False))
