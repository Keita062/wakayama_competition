"""ステップ0：市区町村の類型を決める。

6変数（人口・人口密度は対数）を標準化し、k=1〜12 で k-means。エルボー（k=1とk=12を結ぶ直線から最も離れた点）で k を決め、
人口密度の中央値が高い順に「都市部」「地方の中心都市」「農山村の小都市」と名前を付ける。
出力：01_類型.csv、01_エルボー.csv、01_近い市町村.csv（和歌山6市と構造が近い同じ類型の市町村 上位8）
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from common import KINKI, OUT, TYPE_NAMES, TYPE_VARS, WAKAYAMA6, load_kpi, save

rows = pd.read_csv(OUT / "00_分析対象行.csv", dtype={"市区町村コード": str})
kpi = load_kpi().set_index("市区町村コード")
m = kpi.loc[rows["市区町村コード"].unique(), ["都道府県", "市区町村"] + TYPE_VARS].copy()

X = m[TYPE_VARS].copy()
X["人口"] = np.log(X["人口"])
X["人口密度"] = np.log(X["人口密度"])
Z = (X - X.mean()) / X.std(ddof=0)

# エルボー法
ks = list(range(1, 13))
inertia = [KMeans(n_clusters=k, n_init=50, random_state=0).fit(Z).inertia_ for k in ks]
p1, p2 = np.array([1, inertia[0]]), np.array([12, inertia[-1]])
d12 = p2 - p1
dist = [abs(d12[0] * (p1[1] - v) - d12[1] * (p1[0] - k)) / np.linalg.norm(d12) for k, v in zip(ks, inertia)]
k_best = ks[int(np.argmax(dist))]
save(pd.DataFrame({"k": ks, "クラスタ内平方和": inertia, "直線からの距離": dist, "採用": [k == k_best for k in ks]}), "01_エルボー.csv")

km = KMeans(n_clusters=k_best, n_init=50, random_state=0).fit(Z)
m["cluster"] = km.labels_
order = m.groupby("cluster")["人口密度"].median().sort_values(ascending=False).index
names = dict(zip(order, TYPE_NAMES[:k_best] if k_best == 3 else [f"類型{i + 1}" for i in range(k_best)]))
m["類型"] = m["cluster"].map(names)
save(m.drop(columns="cluster").reset_index(), "01_類型.csv")

# 和歌山6市と構造が近い市町村（同じ類型の中で、標準化した6変数のユークリッド距離が近い順）
near = []
for city in WAKAYAMA6:
    code = m.index[(m["都道府県"] == "和歌山県") & (m["市区町村"] == city)][0]
    same = m.index[m["類型"] == m.loc[code, "類型"]]
    d = np.sqrt(((Z.loc[same] - Z.loc[code]) ** 2).sum(axis=1)).drop(code).sort_values()
    for rank, c in enumerate(d.index[:8], 1):
        near.append((city, rank, m.loc[c, "都道府県"], m.loc[c, "市区町村"], m.loc[c, "人口"], d[c]))
save(pd.DataFrame(near, columns=["市", "順位", "都道府県", "市区町村", "人口", "距離"]), "01_近い市町村.csv")

print("k =", k_best)
print(m["類型"].value_counts().to_string())
print("近畿:", m[m["都道府県"].isin(KINKI)]["類型"].value_counts().to_dict())
print(m[m["都道府県"] == "和歌山県"][["市区町村", "類型"]].to_string())
