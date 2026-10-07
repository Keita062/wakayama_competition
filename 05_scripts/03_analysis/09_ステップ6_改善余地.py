"""ステップ6：ターゲットの市の重点分野で、効いた変数をどこまで伸ばせるか（改善余地）を確かめ、伸ばす数値を決める。

1. 現状：市の値（年度ごとに値がある変数は年度版2023〜26に対応する年の平均）と、同じ類型の中での位置（望ましい向きにそろえ、下から何%か）
2. 目標と伸びしろ：同じ類型の上位4分の1（望ましい向きの75パーセンタイル）までの差。すでに上回っていれば0
3. 伸ばす数値：次の3つをすべて満たす変数
   - 効く：改善候補②の最終モデルで効いた（市町村単位のブートストラップで想定どおりの向きが90%以上）
   - 施策で動かせる（common.CONTROL）
   - 伸びしろがある
   因果の確認（ステップ5）で、主観スコアか幸福度に逆向きに有意な変数は除く
出力：09_改善余地.csv（重点分野の全変数）
"""
import pandas as pd

from common import OUT, load_focus, save

values = pd.read_csv(OUT / "07_変数の値.csv", dtype={"市区町村コード": str})
coef = pd.read_csv(OUT / "07_変数の係数.csv")
fe = pd.read_csv(OUT / "08_因果_係数.csv")
typ = pd.read_csv(OUT / "01_類型.csv", dtype={"市区町村コード": str}).set_index("市区町村コード")["類型"]

fs = fe.groupby("列名").agg(想定どおり有意=("想定どおり有意", "any"), 逆向きに有意=("逆向きに有意", "any"))


def causal(c):
    if c not in fs.index:
        return "1時点のみ（確かめられない）"
    return "逆向きに有意" if fs.loc[c, "逆向きに有意"] else "想定どおりに有意" if fs.loc[c, "想定どおり有意"] else "判別できず"


out = []
for city, field in load_focus().items():
    v = values[values["分野"] == field]
    now = v.groupby(["列名", "市区町村コード"])["値"].mean()
    code = v.loc[(v["都道府県"] == "和歌山県") & (v["市区町村"] == city), "市区町村コード"].iloc[0]
    same = typ.index[typ == typ[code]]
    for _, cf in coef[coef["分野"] == field].iterrows():
        c, sign = cf["列名"], cf["望ましい向き"]
        x = now[c].reindex(same).dropna()
        s = sign * x
        target = sign * s.quantile(0.75)
        out.append({
            "市": city, "類型": typ[code], "分野": field, "列名": c, "表示名": cf["表示名"], "種別": cf["種別"], "望ましい向き": sign,
            "効いた": cf["効いた"], "想定どおりの向きの割合": cf["想定どおりの向きの割合"],
            "操作可能性": cf["操作可能性"], "操作可能性の理由": cf["操作可能性の理由"],
            "市の値": x[code], "類型中央値": x.median(), "目標_類型の上位4分の1": target,
            "類型内%": s.rank(method="max")[code] / len(s) * 100, "伸びしろ": max(0.0, sign * (target - x[code])),
            "因果の確認": causal(c),
        })
res = pd.DataFrame(out)
res["伸ばす数値"] = res["効いた"] & (res["操作可能性"] == "動かせる") & (res["伸びしろ"] > 0) & (res["因果の確認"] != "逆向きに有意")
res = res.sort_values(["市", "伸ばす数値", "効いた", "類型内%"], ascending=[True, False, False, True])
save(res, "09_改善余地.csv")
print(res[["市", "表示名", "効いた", "操作可能性", "市の値", "目標_類型の上位4分の1", "類型内%", "伸びしろ", "因果の確認", "伸ばす数値"]].round(2).to_string(index=False))
