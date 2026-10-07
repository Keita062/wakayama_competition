"""区分のステップ6：ターゲット層の重点分野で、効いた変数の伸びしろを確かめ、伸ばす数値を決める。方法は既存の 09_ステップ6_改善余地.py と同じ。

1. 現状：市の値（年度ごとに値がある変数は年度版2023〜26の平均）と、同じ類型の中での位置（望ましい向きにそろえ、下から何%か）。
   変数は市町村の値なので、区分によらない。
2. 目標と伸びしろ：同じ類型の上位4分の1（望ましい向きの75パーセンタイル）までの差。すでに上回っていれば0。
3. 伸ばす数値：ターゲット層のモデル（04_変数の係数.csv の範囲＝ターゲット層）で効いた・施策で動かせる・伸びしろがある変数。
   ターゲット層の因果の確認（05）で逆向きに有意な変数は除く。
あわせて、全区分のモデルで効いたか（ターゲット層だけで効くのか、全体でも効くのか）を並べる。
出力：06_伸ばす数値.csv
"""
import numpy as np
import pandas as pd

from seg_common import SEG_OUT, load_extra, save
from common import KPIS, OUT, TYPE_VARS
from explain import build

best = pd.read_csv(SEG_OUT / "03_ターゲット層.csv")
coef = pd.read_csv(SEG_OUT / "04_変数の係数.csv")
fe = pd.read_csv(SEG_OUT / "05_因果_係数.csv")
extra, defs = load_extra()
typ = pd.read_csv(OUT / "01_類型.csv", dtype={"市区町村コード": str}).set_index("市区町村コード")["類型"]


def causal(city, c):
    f = fe[(fe["市"] == city) & (fe["列名"] == c)] if len(fe) else fe
    if f.empty:
        return "1時点のみ（確かめられない）"
    return "逆向きに有意" if f["逆向きに有意"].any() else "想定どおりに有意" if f["想定どおり有意"].any() else "判別できず"


out = []
for _, t in best.iterrows():
    city, field = t["市"], t["分野"]
    cf = coef[(coef["市"] == city) & (coef["範囲"] == "ターゲット層")]
    if cf.empty:
        continue
    allc = coef[(coef["市"] == city) & (coef["範囲"] == "全区分")].set_index("列名")
    cols = cf["列名"].tolist()
    xcols = [c for c in cols if c not in KPIS]
    v = build(field, cols, extra if xcols else None)
    now = v.groupby("市区町村コード")[cols].mean()
    code = v.loc[(v["都道府県"] == "和歌山県") & (v["市区町村"] == city), "市区町村コード"].iloc[0]
    same = typ.index[typ == typ[code]]
    for _, r in cf.iterrows():
        c, sign = r["列名"], r["望ましい向き"]
        x = now[c].reindex(same).dropna()
        if code not in x.index:
            continue
        s = sign * x
        target = sign * s.quantile(0.75)
        out.append({
            "市": city, "類型": typ[code], "分野": field, "層": t["層"], "列名": c, "表示名": r["表示名"], "種別": r["種別"], "望ましい向き": sign,
            "係数_1SD": r["係数_1SD"], "効いた": r["効いた"], "想定どおりの向きの割合": r["想定どおりの向きの割合"],
            "全区分の係数_1SD": allc.loc[c, "係数_1SD"] if c in allc.index else np.nan,
            "全区分で効いた": bool(allc.loc[c, "効いた"]) if c in allc.index else False,
            "操作可能性": r["操作可能性"],
            "市の値": x[code], "類型中央値": x.median(), "目標_類型の上位4分の1": target,
            "類型内%": s.rank(method="max")[code] / len(s) * 100, "伸びしろ": max(0.0, sign * (target - x[code])),
            "因果の確認": causal(city, c),
        })
res = pd.DataFrame(out)
res["伸ばす数値"] = res["効いた"] & (res["操作可能性"] == "動かせる") & (res["伸びしろ"] > 0) & (res["因果の確認"] != "逆向きに有意")
res = res.sort_values(["市", "伸ばす数値", "効いた", "類型内%"], ascending=[True, False, False, True])
save(res, "06_伸ばす数値.csv")
print(res[["市", "表示名", "係数_1SD", "効いた", "全区分で効いた", "操作可能性", "市の値", "目標_類型の上位4分の1", "類型内%", "伸びしろ",
           "因果の確認", "伸ばす数値"]].round(2).to_string(index=False))
