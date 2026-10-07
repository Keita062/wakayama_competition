"""前処理：分析に使う行（年代×性別）を決める。

条件：区分＝年代×性別 × 2023〜26年度 × 政令市の区を除く（政令市は市全体の1行、東京23区は区ごと） × 同じ年度の客観24分野がすべてある × 回答者5人以上
出力：04_data/03_analysis/00_分析対象行.csv（PDF：17,609行・680市町村）、00_前処理_件数.csv
"""
import pandas as pd

from common import OBJ, SUBJ, load_kpi, load_wb, save, with_name

s, o = load_wb()
s, o = with_name(s), with_name(o)
kpi = load_kpi()[["市区町村コード", "都道府県", "市区町村", "区分"]].rename(columns={"市区町村": "name", "区分": "自治体区分"})

steps = []
x = s[s["区分"] == "年代×性別"]
steps.append(("年代×性別の行すべて", x))
x = x[x["年度"].between(2023, 2026)]
steps.append(("2023〜26年度", x))
# 政令市の区は個別KPI表に行がないので内部結合で落ちる（政令市は市全体の行を使う。区まで入れると二重に数える）。東京23区は区ごとに入れる
m = x.merge(kpi, on=["都道府県", "name"], how="left", indicator=True)
ward, x = m[m["_merge"] == "left_only"], m[m["_merge"] == "both"].drop(columns="_merge")
steps.append(("政令市の区を除く（政令市は市全体の1行）", x))
obj_ok = o[o[OBJ].notna().all(axis=1)][["年度", "地域ID"] + OBJ]
# 政令市の区の行を使えるかの確認：回答者数（5人以上の割合）と、客観24分野スコアの有無
city = x[x["自治体区分"] == "政令市"]
save(pd.DataFrame([
    ("政令市の区", ward["name"].nunique(), len(ward), (ward["回答者数"] >= 5).mean() * 100, ward.merge(obj_ok, on=["年度", "地域ID"]).shape[0]),
    ("政令市全域", city["name"].nunique(), len(city), (city["回答者数"] >= 5).mean() * 100, city.merge(obj_ok, on=["年度", "地域ID"]).shape[0]),
], columns=["行の種類", "地域数", "行数", "回答者5人以上の割合%", "客観24分野がそろう行数"]), "00_政令市の区.csv")
x = x.merge(obj_ok, on=["年度", "地域ID"], how="inner")
steps.append(("同じ年度の客観データ（24分野すべて）がある", x))
x = x[x["回答者数"] >= 5]
steps.append(("回答者5人以上", x))

cols = ["市区町村コード", "都道府県", "name", "自治体区分", "地域ID", "年度", "年代", "性別", "回答者数", "幸福度"] + SUBJ + OBJ
rows = x[cols].rename(columns={"name": "市区町村"}).reset_index(drop=True)
save(rows, "00_分析対象行.csv")

# 分析対象680市町村の客観24分野スコア（年度ごと。アンケートの有無に関係なく）
codes = rows["市区町村コード"].unique()
ob = o.merge(kpi, on=["都道府県", "name"], how="inner")
ob = ob[ob["市区町村コード"].isin(codes) & ob["年度"].between(2023, 2026)]
save(ob[["市区町村コード", "都道府県", "name", "年度"] + OBJ].rename(columns={"name": "市区町村"}), "00_客観スコア.csv")

counts = pd.DataFrame([(lab, len(d), d["地域ID"].nunique()) for lab, d in steps], columns=["条件", "行数", "地域数"])
w = rows[rows["都道府県"] == "和歌山県"]
counts.loc[len(counts)] = ["うち和歌山県", len(w), w["市区町村コード"].nunique()]
save(counts, "00_前処理_件数.csv")
print(counts.to_string(index=False))
print("和歌山県で残る市:", w["市区町村"].unique().tolist())
