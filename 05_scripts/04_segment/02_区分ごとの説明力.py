"""区分のステップ3：性別×年代ごとに、幸福度を主観24分野で説明するElastic Net回帰を行い、各分野の説明力（取り分）を出す。

既存のステップ3（04_ステップ3_寄与度.py）と同じ方法を、区分ごとの行だけで行う：
  1. 各行の幸福度・主観24分野から、同じ「類型×年度×年代×性別」の平均を引く
  2. 平均0・ばらつき1に標準化（回答者数で重みづけ）
  3. Elastic Net回帰（alpha・l1_ratioは市町村単位の5分割交差検証、common.elastic_net）
  4. 取り分＝係数の絶対値の割合（%）。係数がマイナスの分野はマイナスの取り分として扱う（ステップ4と同じ）
区分ごとの行は全国で約1,000〜4,000行のため、類型ごとには分けず、類型をそろえた全国で推定する。
出力：02_区分ごとの説明力.csv、02_区分ごとのモデル.csv
"""
import numpy as np
import pandas as pd

from seg_common import SEGS, load_seg_rows, resid, save
from common import FIELDS, SUBJ, elastic_net


def standardize(a, w):
    m = np.average(a, axis=0, weights=w)
    return (a - m) / np.sqrt(np.average((a - m) ** 2, axis=0, weights=w))


rows = load_seg_rows()
r = resid(rows, ["幸福度"] + SUBJ)
out, models = [], []
for seg in SEGS:
    d = r[r["区分"] == seg].reset_index(drop=True)
    w = d["回答者数"].values.astype(float)
    y, X = standardize(d[["幸福度"]].values, w)[:, 0], standardize(d[SUBJ].values, w)
    en, cv, _ = elastic_net(X, y, w, d["市区町村コード"].values)
    share = np.abs(en.coef_) / np.abs(en.coef_).sum() * 100
    models.append((seg, len(d), d["市区町村コード"].nunique(), int(d["回答者数"].sum()), cv, en.alpha_, en.l1_ratio_))
    rank = pd.Series(-share).rank(method="min").astype(int).values
    for f, c, s, rk in zip(FIELDS, en.coef_, share, rank):
        out.append((seg, f, c, s, s * np.sign(c), rk))
    print(seg, len(d), round(cv, 3))
res = pd.DataFrame(out, columns=["区分", "分野", "標準化係数", "取り分%", "向き付きの取り分%", "順位"])
save(res, "02_区分ごとの説明力.csv")
save(pd.DataFrame(models, columns=["区分", "行数", "市町村数", "回答者数", "交差検証R2", "alpha", "l1_ratio"]), "02_区分ごとのモデル.csv")
print(res.pivot_table(index="分野", columns="区分", values="取り分%").reindex(columns=SEGS).round(0).to_string())
