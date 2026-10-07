"""改善候補②：個別KPIでは説明できなかった重点分野について、追加の変数（オープンデータ）を入れて主観スコアを説明できるかを確かめる。

追加の変数：05_scripts/02_build/03_追加変数の作成.py が作る 04_data/02_processed/03_追加変数.csv（定義は _定義.csv）。
  重点分野の設問（例：地域とのつながり＝町内の人への信頼・コミュニティ活動への参加・相談できる人・愛着、
  自己効力感＝自分のことを好ましく感じる）から、関わりそうな変数を仮説として選んだもの。
比べる3つのモデル（Elastic Net回帰。方法は explain.py。どれも同じ行＝追加の変数まですべてそろう市町村×年度で比べる）：
  - 土台：類型＋類型の6変数＋年度
  - 土台＋その分野の個別KPI
  - 土台＋その分野の個別KPI＋追加の変数
判定：土台に対する最終モデルの上乗せの95%信頼区間（市町村単位のブートストラップ）の下限が0を超えれば「説明できる」。
  あわせて、個別KPIのモデルに対する追加の変数の上乗せも同じ方法で確かめる。
最後のモデルで効いた変数（ブートストラップで想定どおりの向きが90%以上）を、伸ばす数値の候補にする。
出力：07_説明力.csv、07_変数の係数.csv、07_変数の値.csv（重点分野の変数の、市町村×年度の値）
"""
import numpy as np
import pandas as pd

from common import CONTROL, KPIS, PROCESSED, TYPE_VARS, load_focus, save
from explain import build, fit, lift_test

extra = pd.read_csv(PROCESSED / "03_追加変数.csv", dtype={"市区町村コード": str})
defs = pd.read_csv(PROCESSED / "03_追加変数_定義.csv").set_index("列名")
judge1 = pd.read_csv(PROCESSED.parent / "03_analysis" / "06_説明力.csv").set_index("分野")["判定"]
focus = load_focus()

models, coefs, values = [], [], []
for field in dict.fromkeys(focus.values()):
    kcols = [c for c, (f, _, _) in KPIS.items() if f == field]
    xcols = defs.index[defs["分野"] == field].tolist()
    signs = {c: KPIS[c][1] for c in kcols} | {c: int(defs.loc[c, "望ましい向き"]) for c in xcols}
    d = build(field, kcols + xcols, extra)
    d = d.dropna(subset=["主観スコア"] + TYPE_VARS + kcols + xcols).reset_index(drop=True)
    r0, _, _, p0 = fit(d, [], {})
    r1, _, _, p1 = fit(d, kcols, signs)
    r2, en, coef, p2 = fit(d, kcols + xcols, signs)
    lift, lo, hi, pv, r0, r2 = lift_test(d, p0, p2)
    lx, lxl, lxh, pxv, r1, _ = lift_test(d, p1, p2)
    models.append((field, "・".join(c for c, f in focus.items() if f == field), judge1.get(field), len(d), d["市区町村コード"].nunique(),
                   r0, r1, r2, lift, lo, hi, pv, lx, lxl, lxh, en.alpha_, en.l1_ratio_))
    coef.insert(0, "分野", field)
    coef["種別"] = ["個別KPI" if c in kcols else "追加の変数" for c in coef["列名"]]
    coefs.append(coef)
    v = d.melt(id_vars=["市区町村コード", "都道府県", "市区町村", "類型", "年度"], value_vars=kcols + xcols, var_name="列名", value_name="値")
    v.insert(0, "分野", field)
    values.append(v)
m = pd.DataFrame(models, columns=["分野", "重点分野の市", "改善候補①の判定", "行数", "市町村数", "土台_交差検証R2%", "土台＋個別KPI_交差検証R2%",
                                  "土台＋個別KPI＋追加の変数_交差検証R2%", "上乗せ", "上乗せ_下限95", "上乗せ_上限95", "p値_片側",
                                  "追加の変数の上乗せ", "追加の変数の上乗せ_下限95", "追加の変数の上乗せ_上限95", "alpha", "l1_ratio"])
m["判定"] = np.where(m["上乗せ_下限95"] > 0, "説明できる", "説明できない")
c = pd.concat(coefs)
c["表示名"] = c["列名"].map(lambda x: KPIS[x][2] if x in KPIS else defs.loc[x, "表示名"])
c["操作可能性"] = c["列名"].map(lambda x: CONTROL[x][0])
c["操作可能性の理由"] = c["列名"].map(lambda x: CONTROL[x][1])
save(m, "07_説明力.csv")
save(c, "07_変数の係数.csv")
save(pd.concat(values), "07_変数の値.csv")
print(m.round(2).to_string(index=False))
print(c.round(3).to_string(index=False))
