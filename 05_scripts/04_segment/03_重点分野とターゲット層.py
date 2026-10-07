"""区分のステップ4：ターゲットの市ごとに、性別×年代の区分ごとの下振れと説明力から、重点分野とターゲット層（性別×年代）を決める。

1. 下振れ（区分ごと）：既存のステップ4と同じく、行ごとに主観24分野・客観24分野をそれぞれ24分野の中で標準化し、
   分野ごとに「主観−客観」を出して、同じ「類型×年度×年代×性別」の平均を引く。市×区分ごとに年度をまとめて回答者数で
   重みづけ平均し、経験ベイズで縮める（seg_common.shrink。回答者が少ない区分ほど0＝類型の平均に近づく）。
2. 説明力（区分ごと）：02_区分ごとの説明力.csv の向き付きの取り分%。
3. 確かな下振れ＝縮めた下振れ＋1.28×標準誤差（90%の確率で、少なくともこれだけは下振れている、という控えめな値）。
   回答者が多い区分は標準誤差が小さく、下振れがほぼそのまま残る。少ない区分は大きく割り引かれ、0以上なら下振れとみなさない。
   さらに、回答が1年度しかない区分は、その年の回答者の偏りを避けるため下振れとみなさない（2年度以上の回答を条件にする）。
   重点度（市×区分×分野）：第二象限（2年度以上の回答があり、確かな下振れ＜0 かつ 説明力＞均等割り 100/24%）なら
   説明力×（−確かな下振れ）、それ以外は0。
4. インパクト＝重点度×その区分の人口（国勢調査2020）。人口が多い区分ほど、主観スコアが上がったときに幸福度が上がる人が多い。
5. ターゲット層：同じ性別で年代が続く区分、または男女両方で年代が続く区分をまとめた「層」を候補とし、
   層に入るすべての区分が第二象限にある（＝その分野がどの区分にも刺さる）層の中で、インパクトの合計が最大の「分野×層」を選ぶ。
   隣り合う区分で同じ分野が弱ければ大きな層にまとまり（標本・人口が大きくなる）、弱くない区分は層に入らない。
出力：03_区分ごとの下振れ.csv（ターゲットの市×10区分×24分野）、03_区分マトリクス.csv、03_層の候補.csv、03_ターゲット層.csv
"""
import numpy as np
import pandas as pd

from seg_common import AGES, SEGS, SEXES, SEG_OUT, load_pop, load_seg_rows, resid, save, shrink, targets
from common import FIELDS, OBJ, SUBJ

Y_LINE = 100 / len(FIELDS)
rows = load_seg_rows()


def zrow(df):
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1, ddof=0), axis=0)


gap = pd.DataFrame(zrow(rows[SUBJ]).values - zrow(rows[OBJ]).values, columns=FIELDS)
gap = pd.concat([rows[["市区町村コード", "都道府県", "市区町村", "類型", "年度", "年代", "性別", "区分", "回答者数"]], gap], axis=1)
r = resid(gap, FIELDS)
tg = targets()
codes = {c: rows.loc[(rows["都道府県"] == "和歌山県") & (rows["市区町村"] == c), "市区町村コード"].iloc[0] for c in tg}

low = []
for f in FIELDS:
    s = shrink(r, f)
    s = s[s["市区町村コード"].isin(codes.values())]
    s["分野"] = f
    low.append(s)
low = pd.concat(low)
low["市"] = low["市区町村コード"].map({v: k for k, v in codes.items()})
save(low, "03_区分ごとの下振れ.csv")

share = pd.read_csv(SEG_OUT / "02_区分ごとの説明力.csv").set_index(["区分", "分野"])["向き付きの取り分%"]
pop = load_pop().set_index(["市区町村コード", "区分"])["人口"]
m = low.rename(columns={"縮めた値": "下振れ"})[["市", "市区町村コード", "区分", "分野", "生の値", "下振れ", "標準誤差", "回答者数"]].copy()
m["説明力"] = [share.get((s, f), np.nan) for s, f in zip(m["区分"], m["分野"])]
Z90 = 1.2816  # 片側90%
m["確かな下振れ"] = m["下振れ"] + Z90 * m["標準誤差"]
yrs = rows.groupby(["市区町村コード", "区分"])["年度"].nunique()
m["回答の年度数"] = [yrs.get((c, s), 0) for c, s in zip(m["市区町村コード"], m["区分"])]
m["第二象限"] = (m["回答の年度数"] >= 2) & (m["確かな下振れ"] < 0) & (m["説明力"] > Y_LINE)
m["重点度"] = np.where(m["第二象限"], m["説明力"] * -m["確かな下振れ"], 0.0)
m["人口"] = [pop.get((c, s), np.nan) for c, s in zip(m["市区町村コード"], m["区分"])]
m["インパクト"] = m["重点度"] * m["人口"]
save(m, "03_区分マトリクス.csv")

# 層の候補：性別（女性・男性・男女）×続く年代
cands = []
for city in tg:
    mc = m[m["市"] == city].set_index(["区分", "分野"])
    for f in FIELDS:
        for sex in SEXES + ["男女"]:
            sx = SEXES if sex == "男女" else [sex]
            for i in range(len(AGES)):
                for j in range(i, len(AGES)):
                    segs = [f"{s}・{a}" for s in sx for a in AGES[i:j + 1]]
                    if not all((s, f) in mc.index for s in segs):
                        continue  # 回答者がいない区分を含む
                    d = mc.loc[[(s, f) for s in segs]]
                    if not d["第二象限"].all():
                        continue
                    ages = AGES[i] if i == j else f"{AGES[i][:2]}〜{AGES[j].replace('20〜30代', '30代')}"
                    cands.append((city, f, f"{sex}・{ages}", sex, AGES[i], AGES[j], len(segs), "・".join(segs),
                                  d["人口"].sum(), d["回答者数"].sum(), d["インパクト"].sum(),
                                  np.average(d["下振れ"], weights=d["人口"]), np.average(d["確かな下振れ"], weights=d["人口"]),
                                  np.average(d["説明力"], weights=d["人口"])))
cand = pd.DataFrame(cands, columns=["市", "分野", "層", "性別", "年代_から", "年代_まで", "区分の数", "区分", "人口", "回答者数",
                                    "インパクト", "下振れ_人口で平均", "確かな下振れ_人口で平均", "説明力_人口で平均"])
cand["インパクト_市内の最大を100"] = cand["インパクト"] / cand.groupby("市")["インパクト"].transform("max") * 100
cand = cand.sort_values(["市", "インパクト"], ascending=[True, False])
save(cand, "03_層の候補.csv")
best = cand.groupby("市").head(1)
save(best, "03_ターゲット層.csv")
print(cand.groupby("市").head(8).round(2).to_string(index=False))
print(m[m["第二象限"]].groupby(["市", "分野"])["インパクト"].sum().sort_values(ascending=False).groupby("市").head(5).round(0))
