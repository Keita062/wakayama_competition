"""ステップ1：和歌山の6市の、全国の中での順位（年度ごとのパーセンタイル）。

指標：幸福度・主観24分野平均（年代×性別の構成をそろえた値）、客観24分野平均。
各年度、分析対象の市町村の中で低いほうから数えた位置（0〜100）を出す。
出力：02_全国順位.csv（6市×年度×指標）、02_年度別市町村数.csv
"""
import pandas as pd

from common import OBJ, SUBJ, WAKAYAMA6, city_values, load_rows, pct_rank, save

rows = load_rows()
rows["主観24分野平均"] = rows[SUBJ].mean(axis=1)
rows["客観24分野平均"] = rows[OBJ].mean(axis=1)

v = city_values(rows, ["幸福度", "主観24分野平均"], by=("年度", "市区町村コード"))
v["客観24分野平均"] = rows.groupby(["年度", "市区町村コード"])["客観24分野平均"].first()
v = v.reset_index()

out = []
for year, g in v.groupby("年度"):
    g = g.set_index("市区町村コード")
    for col in ["幸福度", "主観24分野平均", "客観24分野平均"]:
        p = pct_rank(g[col])
        for code in g.index:
            out.append((year, code, col, g.loc[code, col], p[code]))
res = pd.DataFrame(out, columns=["年度", "市区町村コード", "指標", "値", "パーセンタイル"])
names = rows.drop_duplicates("市区町村コード").set_index("市区町村コード")[["都道府県", "市区町村"]]
res = res.join(names, on="市区町村コード")
w = res[(res["都道府県"] == "和歌山県") & res["市区町村"].isin(WAKAYAMA6)]
save(w, "02_全国順位.csv")
save(v.groupby("年度").size().rename("市町村数").reset_index(), "02_年度別市町村数.csv")
print(v.groupby("年度").size().to_dict())
print(w.pivot_table(index=["指標", "市区町村"], columns="年度", values="パーセンタイル").round(0).to_string())
