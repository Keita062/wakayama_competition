"""区分のステップ1：和歌山6市の性別×年代ごとの立ち位置（同じ類型・同じ区分の市町村と比べる）。

1. 各行（市町村×年度×年代×性別）の幸福度・主観24分野平均から、同じ「類型×年度×年代×性別」の平均を引く（seg_common.resid）。
2. 市×区分ごとに、年度をまとめて回答者数で重みづけ平均し、経験ベイズで縮める（seg_common.shrink）。
   1つの市×区分の回答者は数十人のため、生の値は偶然で大きく振れる。回答者が少ないほど、類型の平均（0）に近づける。
3. 同じ類型・同じ区分の市町村の中で、縮めた値が下から何%の位置か（類型内%。低いほど弱い）を出す。
出力：01_区分の立ち位置.csv（全市町村×10区分×2指標）、01_和歌山6市.csv
"""
import numpy as np
import pandas as pd

from seg_common import SEGS, load_seg_rows, resid, save, shrink, wakayama6
from common import SUBJ

rows = load_seg_rows()
rows["主観24分野平均"] = rows[SUBJ].mean(axis=1)
r = resid(rows, ["幸福度", "主観24分野平均"])
info = rows.drop_duplicates("市区町村コード").set_index("市区町村コード")[["都道府県", "市区町村", "類型"]]

out = []
for ind in ["幸福度", "主観24分野平均"]:
    s = shrink(r, ind).join(info, on="市区町村コード")
    s["指標"] = ind
    s["類型内%"] = s.groupby(["類型", "区分"])["縮めた値"].rank(pct=True) * 100
    s["類型内の市町村数"] = s.groupby(["類型", "区分"])["縮めた値"].transform("size")
    out.append(s)
res = pd.concat(out)
save(res, "01_区分の立ち位置.csv")

j = wakayama6()[["市", "類型", "判定"]]
w6 = res[(res["都道府県"] == "和歌山県") & res["市区町村"].isin(j["市"])].merge(j, left_on=["市区町村", "類型"], right_on=["市", "類型"])
save(w6, "01_和歌山6市.csv")
for ind in ["幸福度", "主観24分野平均"]:
    print(ind)
    print(w6[w6["指標"] == ind].pivot_table(index="市", columns="区分", values="類型内%").reindex(columns=SEGS).round(0).to_string())
    print(w6[w6["指標"] == ind].pivot_table(index="市", columns="区分", values="回答者数").reindex(columns=SEGS).to_string())
