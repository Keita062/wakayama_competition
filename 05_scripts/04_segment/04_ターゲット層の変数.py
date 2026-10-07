"""区分の改善候補①②：ターゲット層（03_ターゲット層.csv）の重点分野の主観スコアを、その分野の変数（個別KPI・追加の変数）で
説明できるか、どの変数が効くかを、ターゲット層の行だけで確かめる（Elastic Net回帰。方法は既存の explain.py と同じ）。

データ：全国の市町村×年度×年代×性別の行のうち、ターゲット層の区分に入る行（回答者5人以上）。
  - 目的変数：その行の重点分野の主観スコア（その性別×年代の回答者の平均）
  - 説明変数：市町村×年度の変数（既存の改善候補①②と同じ値。年度ごとに値があるものは Y−1年の値）
  - 重み：回答者数。交差検証・ブートストラップは市町村単位
比べるモデル：
  - 土台：類型（ダミー）＋類型の6変数＋年度（ダミー）＋年代×性別（ダミー。層の中の構成の違いをそろえる）
  - 土台＋個別KPI
  - 土台＋個別KPI＋追加の変数（追加の変数がある分野のみ）
判定：土台に対する最終モデルの交差検証R²の上乗せの95%信頼区間（市町村単位のブートストラップ、explain.lift_test）の下限が0を超えれば「説明できる」。
効いた変数：市町村単位のブートストラップで想定どおりの向きが90%以上。
あわせて、全区分（全年代・男女）で同じモデルを推定し、ターゲット層と係数を比べる。
出力：04_説明力.csv、04_変数の係数.csv
"""
import sys

import numpy as np
import pandas as pd

from seg_common import SEG_OUT, load_extra, load_seg_rows, save
from common import CONTROL, KPIS, TYPE_VARS, elastic_net, stability
from explain import build, lift_test, zs

STABLE = 0.9
extra, defs = load_extra()
best = pd.read_csv(SEG_OUT / "03_ターゲット層.csv")
if len(sys.argv) > 1:  # 市を指定して一部だけ試すとき
    best = best[best["市"].isin(sys.argv[1:])]
rows = load_seg_rows()


def design(d, cols):
    return pd.concat([pd.get_dummies(d["類型"], drop_first=True), pd.get_dummies(d["年度"], prefix="年度", drop_first=True),
                      pd.get_dummies(d["性別"] + d["年代"], drop_first=True), d[TYPE_VARS], d[cols]], axis=1).astype(float)


def fit(d, cols, signs):
    X = design(d, cols)
    y, w, g = d["主観スコア"].values, d["回答者数"].values.astype(float), d["市区町村コード"].values
    en, r2, oof = elastic_net(zs(X).values, y, w, g)
    coef = pd.DataFrame()
    if cols:
        pos, neg = stability(zs(X).values, y, w, g, en.alpha_, en.l1_ratio_)
        j = [list(X.columns).index(c) for c in cols]
        coef = pd.DataFrame({"列名": cols, "望ましい向き": [signs[c] for c in cols], "係数_1SD": en.coef_[j],
                             "想定どおりの向きの割合": [(pos if signs[c] > 0 else neg)[i] for c, i in zip(cols, j)]})
        coef["効いた"] = coef["想定どおりの向きの割合"] >= STABLE
    pred = d[["市区町村コード", "年度"]].copy()
    pred["交差検証の予測"] = oof
    return r2, en, coef, pred


models, coefs = [], []
for _, t in best.iterrows():
    field, segs = t["分野"], t["区分"].split("・")
    segs = [f"{a}・{b}" for a, b in zip(segs[0::2], segs[1::2])]  # 「女性・40代・女性・50代」→ ["女性・40代", "女性・50代"]
    kcols = [c for c, (f, _, _) in KPIS.items() if f == field]
    xcols = defs.index[defs["分野"] == field].tolist()
    signs = {c: KPIS[c][1] for c in kcols} | {c: int(defs.loc[c, "望ましい向き"]) for c in xcols}
    allc = kcols + xcols
    cy = build(field, allc, extra if xcols else None).drop(columns=["主観スコア", "回答者数", "都道府県", "市区町村"])
    for scope, rr in [("ターゲット層", rows[rows["区分"].isin(segs)]), ("全区分", rows)]:
        d = rr[["市区町村コード", "年度", "年代", "性別", "回答者数", f"主観_{field}"]].rename(columns={f"主観_{field}": "主観スコア"})
        d = d.merge(cy, on=["市区町村コード", "年度"], how="inner").dropna(subset=["主観スコア"] + TYPE_VARS + allc).reset_index(drop=True)
        r0, _, _, p0 = fit(d, [], {})
        r1, en1, c1, p1 = fit(d, kcols, signs)
        steps = [("土台＋個別KPI", r1, en1, c1, p1)]
        if xcols:
            r2, en2, c2, p2 = fit(d, allc, signs)
            steps.append(("土台＋個別KPI＋追加の変数", r2, en2, c2, p2))
        name, rf, enf, cf, pf = steps[-1]
        lift, lo, hi, pv, r0_, rf_ = lift_test(d.assign(主観スコア=d["主観スコア"]), p0.assign(交差検証の予測=p0["交差検証の予測"]), pf)
        models.append((t["市"], field, t["層"], scope, len(d), d["市区町村コード"].nunique(), int(d["回答者数"].sum()), r0 * 100, r1 * 100,
                       steps[-1][1] * 100 if xcols else np.nan, name, lift, lo, hi, enf.alpha_, enf.l1_ratio_))
        cf.insert(0, "範囲", scope)
        cf.insert(0, "層", t["層"])
        cf.insert(0, "分野", field)
        cf.insert(0, "市", t["市"])
        coefs.append(cf)
        print(t["市"], field, scope, len(d), round(r0 * 100, 1), round(rf * 100, 1), round(lo, 2), round(hi, 2))
m = pd.DataFrame(models, columns=["市", "分野", "層", "範囲", "行数", "市町村数", "回答者数", "土台_交差検証R2%", "土台＋個別KPI_交差検証R2%",
                                  "土台＋個別KPI＋追加の変数_交差検証R2%", "最終モデル", "上乗せ", "上乗せ_下限95", "上乗せ_上限95", "alpha", "l1_ratio"])
m["判定"] = np.where(m["上乗せ_下限95"] > 0, "説明できる", "説明できない")
c = pd.concat(coefs)
c["表示名"] = c["列名"].map(lambda x: KPIS[x][2] if x in KPIS else defs.loc[x, "表示名"])
c["種別"] = c["列名"].map(lambda x: "個別KPI" if x in KPIS else "追加の変数")
c["操作可能性"] = c["列名"].map(lambda x: CONTROL[x][0] if x in KPIS else defs.loc[x, "操作可能性"])
# 市ごとのファイルに保存し、あるものをすべてまとめる（市を指定して別々に実行できるようにする）
for city in m["市"].unique():
    save(m[m["市"] == city], f"04_説明力_{city}.csv")
    save(c[c["市"] == city], f"04_変数の係数_{city}.csv")
for name in ["04_説明力", "04_変数の係数"]:
    save(pd.concat([pd.read_csv(f) for f in sorted(SEG_OUT.glob(f"{name}_*.csv"))]), f"{name}.csv")
print(m.round(2).to_string(index=False))
print(c[c["範囲"] == "ターゲット層"].round(3).to_string(index=False))
