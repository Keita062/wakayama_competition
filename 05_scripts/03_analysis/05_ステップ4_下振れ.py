"""ステップ4：環境（客観）の割に主観スコア（主観）が低い分野＝下振れを探す。

1. 行ごとに主観24分野と客観24分野をそれぞれ平均0・ばらつき1にそろえ（STD_MODE で方式を切り替え）、分野ごとに「主観−客観」を出す
2. 同じ「類型×年度×年代×性別」の平均（回答者数で重みづけ）を引き、都市か地方かの条件をそろえる
3. 市町村ごとに回答者数で平均し、類型内の順位（1位が最も下振れ）を出す。全国版は「年度×年代×性別」の平均を引く
出力：05_下振れ.csv（全市町村×24分野）、05_下振れ_ターゲット.csv
"""
import numpy as np
import pandas as pd

from common import FIELDS, OBJ, OUT, SUBJ, load_rows, save, wmean

STD_MODE = "row"  # "column"：分野ごとに全行で標準化 / "row"：行ごとに24分野で標準化

rows = load_rows()
w = rows["回答者数"].astype(float)


def zscore(df):
    if STD_MODE == "row":
        return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1, ddof=0), axis=0)
    m = df.apply(lambda c: wmean(c, w))
    sd = np.sqrt(((df - m) ** 2).mul(w, axis=0).sum() / w.sum())
    return (df - m) / sd


gap = pd.DataFrame(zscore(rows[SUBJ]).values - zscore(rows[OBJ]).values, columns=FIELDS, index=rows.index)
gap = pd.concat([rows[["市区町村コード", "都道府県", "市区町村", "類型", "年度", "年代", "性別", "回答者数"]], gap], axis=1)


def city_gap(keys):
    d = gap.copy()
    for f in FIELDS:
        gm = gap.groupby(keys).apply(lambda g: wmean(g[f], g["回答者数"]), include_groups=False)
        d[f] = gap[f] - gap.set_index(keys).index.map(gm).values
    return d.groupby("市区町村コード").apply(lambda g: pd.Series({f: wmean(g[f], g["回答者数"]) for f in FIELDS}),
                                          include_groups=False)


by_type = city_gap(["類型", "年度", "年代", "性別"])
national = city_gap(["年度", "年代", "性別"])
info =rows.drop_duplicates("市区町村コード").set_index("市区町村コード")[["都道府県", "市区町村", "類型"]]

long = []
for f in FIELDS:
    t = info.copy()
    t["分野"] = f
    t["下振れ_類型内"] = by_type[f]
    t["類型内順位"] = by_type[f].groupby(info["類型"]).rank(method="min")
    t["下振れ_全国"] = national[f]
    t["全国順位"] = national[f].rank(method="min")
    long.append(t)
long = pd.concat(long).reset_index()
long["類型の市町村数"] = long["類型"].map(info["類型"].value_counts())
save(long, "05_下振れ.csv")

# 類型そのものの平均的な下振れ（全国基準）：「年度×年代×性別」の平均を引いた行を、類型ごとに回答者数で重みづけして平均
nat_rows = gap.copy()
for f in FIELDS:
    gm = gap.groupby(["年度", "年代", "性別"]).apply(lambda g: wmean(g[f], g["回答者数"]), include_groups=False)
    nat_rows[f] = gap[f] - gap.set_index(["年度", "年代", "性別"]).index.map(gm).values
type_mean = nat_rows.groupby("類型").apply(lambda g: pd.Series({f: wmean(g[f], g["回答者数"]) for f in FIELDS}),
                                          include_groups=False)
save(type_mean.reset_index(), "05_類型平均の下振れ.csv")

targets = [("田辺市", "自己効力感"), ("和歌山市", "地域とのつながり"), ("橋本市", "健康状態"),
           ("田辺市", "地域とのつながり"), ("和歌山市", "健康状態")]
t = pd.concat([long[(long["都道府県"] == "和歌山県") & (long["市区町村"] == c) & (long["分野"] == f)] for c, f in targets])
save(t, "05_下振れ_ターゲット.csv")
print(t[["市区町村", "分野", "下振れ_類型内", "類型内順位", "類型の市町村数", "下振れ_全国", "全国順位"]].round(2).to_string())
print(type_mean.loc["農山村の小都市", "自己効力感"].round(2))

# 重点分野：ターゲットの市ごとに、横軸＝下振れ（類型内）、縦軸＝説明力（ステップ3、その市の類型のElastic Netの取り分%）のマトリクスを作る。
# 説明力は係数の向きを付ける（係数がマイナスの分野は、主観スコアが上がっても幸福度は上がらないのでマイナスの取り分とする）。
# 第二象限（下振れ＜0 かつ 説明力＞全分野の均等割り 100/24%）を重点化の候補とし、
# 重点度＝説明力（取り分%）×下振れの大きさ（−下振れ）が最大の1分野を重点分野にする。
# 重点度は「幸福度に効く度合い」と「環境の割に主観スコアが足りない度合い」の積で、どちらか一方が0なら0になる。
imp = pd.read_csv(OUT / "04_寄与度.csv")
judge = pd.read_csv(OUT / "03_6市の判定.csv")
targets = judge[judge["判定"].str.contains("ターゲット")]
Y_LINE = 100 / len(FIELDS)
mat = []
for _, tc in targets.iterrows():
    sh = imp[imp["対象"] == tc["類型"]].set_index("分野")
    g = long[(long["都道府県"] == "和歌山県") & (long["市区町村"] == tc["市"])].set_index("分野")
    for f in FIELDS:
        x, y = g.loc[f, "下振れ_類型内"], sh.loc[f, "取り分%"] * np.sign(sh.loc[f, "標準化係数"])
        q2 = (x < 0) and (y > Y_LINE)
        mat.append((tc["市"], tc["判定"], tc["類型"], f, x, int(g.loc[f, "類型内順位"]), y, q2, y * -x if q2 else np.nan))
mat = pd.DataFrame(mat, columns=["市", "判定", "類型", "分野", "下振れ_類型内", "下振れ_類型内順位", "説明力_取り分%", "第二象限", "重点度"])
mat["重点分野"] = False
for city, g in mat.groupby("市"):
    if g["重点度"].notna().any():
        mat.loc[g["重点度"].idxmax(), "重点分野"] = True
mat["説明力の基準線"] = Y_LINE
save(mat, "05_重点分野マトリクス.csv")
print(mat[mat["第二象限"]].round(2).to_string(index=False))
