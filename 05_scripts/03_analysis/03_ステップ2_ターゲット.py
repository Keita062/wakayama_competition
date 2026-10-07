"""ステップ2：ターゲットの市を決める。

①現状把握：幸福度・主観24分野平均（2023〜26年度をまとめた、年代×性別の構成をそろえた値）の、同じ類型の中での順位（低いほうから）。
  - 広く弱い市：両方とも類型の中央値より低い
  - 特定の分野だけ弱い市：24分野のうち最も順位が低い分野が、類型の下位5%以内
②総合計画：①の候補について、総合計画にその分野の課題が明記されているか（原文を読んで判断。下の PLAN に手入力。
  原文とページは 02_memo/総合計画_要点.md、PDFは 04_data/01_raw/13_総合計画/）。
③絞り込み：①②の3条件（広く弱い・特定の分野だけ弱い・総合計画に明記）を満たす数が多い順に並べ、同数なら
  最も低い分野の類型内の位置（順位÷類型の市町村数）が低い順。上位2市をターゲット（1位＝主、2位＝副）とする。
出力：03_6市の判定.csv、03_市町村別_主観.csv（ステップ3以降でも使う市町村値）
"""
import numpy as np
import pandas as pd

from common import FIELDS, SUBJ, WAKAYAMA6, city_values, load_rows, save

# 総合計画との照合（手入力）：市 → (課題に明記あり, 照合の結果, 要約, 根拠となる原文とページ)
PLAN = {
    "田辺市": (True, "課題に明記あり", "若者が市外へ転出した後、地元へ戻らない傾向",
             "基本理念は「一人ひとりが大切にされ、幸せを実感できるまちづくり」。第3次総合計画 基本構想（案）（R8.7）PDF p7に"
             "「高校卒業後、進学や就職のため、市外へ転出した後、地元へ戻らない傾向が続いており」「町内会加入率の低下などによる地域コミュニティの希薄化」"),
    "和歌山市": (True, "課題に明記あり", "開業率の低さ（事業創造）、女性・高齢者の就業率の低さ（雇用・所得）",
              "第5次長期総合計画 PDF p56に「本市は、開業率と廃業率がともに全国平均より低く、産業の新陳代謝が進みにくい状況にあります」（事業創造）、"
              "PDF p58に「女性及び高齢者の就業率、女性の正規雇用率が低い状況」（雇用・所得）。"
              "PDF p101に「近年、自治会への加入者数が減少するなど人と人とのつながりは希薄化しています」。自治会加入率は80.3%（H27）→73.1%（R5）と目標85.0%から逆行（実施計画R6〜R8 PDF p134）"),
    "橋本市": (True, "課題に明記あり", "雇用・就労の満足度の低さ（雇用・所得）",
             "第2次長期総合計画 後期基本計画 PDF p23に「『雇用、就労、労働環境の整備』…は満足度が低い一方で重要度が高くなっているため、重点的な対応が必要」"),
    "岩出市": (False, "課題に明記なし", "転入超過が続く前提で、幸福度・主観スコアの低さに対応する課題を挙げていない",
             "第3次長期総合計画 後期基本計画（R8.3策定）は転入超過が続いていることを前提にしており、若者の転出も課題にしていない"),
}

rows = load_rows()
rows["主観24分野平均"] = rows[SUBJ].mean(axis=1)
v = city_values(rows, ["幸福度", "主観24分野平均"] + SUBJ)
info = rows.drop_duplicates("市区町村コード").set_index("市区町村コード")[["都道府県", "市区町村", "類型"]]
v = info.join(v)
save(v.reset_index(), "03_市町村別_主観.csv")

out = []
for city in WAKAYAMA6:
    code = v.index[(v["都道府県"] == "和歌山県") & (v["市区町村"] == city)][0]
    g = v[v["類型"] == v.loc[code, "類型"]]
    n = len(g)
    rk = g.rank(numeric_only=True, method="min")  # 1 = 最も低い
    field_rank = rk.loc[code, SUBJ]
    worst = field_rank.idxmin()
    broad = (v.loc[code, "幸福度"] < g["幸福度"].median()) and (v.loc[code, "主観24分野平均"] < g["主観24分野平均"].median())
    specific = field_rank[worst] <= np.ceil(n * 0.05)
    # 条件1・2のどちらにも当たらない市は、弱い分野がないため総合計画を確かめない（満たす条件の数は0）
    stated, plan, short, note = PLAN.get(city, (False, "確かめない（条件1・2に当たらない）", "", ""))
    out.append({
        "市": city, "類型": v.loc[code, "類型"], "類型の市町村数": n,
        "幸福度": v.loc[code, "幸福度"], "幸福度_類型内順位": int(rk.loc[code, "幸福度"]),
        "主観24分野平均": v.loc[code, "主観24分野平均"], "主観平均_類型内順位": int(rk.loc[code, "主観24分野平均"]),
        # 同じ順位で並ぶ分野はすべて「最も低い分野」とする
        "最も低い分野": "、".join(f.replace("主観_", "") for f in field_rank.index[field_rank == field_rank[worst]]),
        "最も低い分野_類型内順位": int(field_rank[worst]),
        "2番目に低い分野": field_rank[field_rank > field_rank[worst]].idxmin().replace("主観_", ""),
        "2番目に低い分野_類型内順位": int(field_rank[field_rank > field_rank[worst]].min()),
        "手順1_広く弱い": broad, "手順2_特定分野だけ弱い": bool(specific),
        "総合計画との照合": plan, "総合計画の要約": short, "総合計画メモ": note,
        "満たす条件の数": int(broad) + int(specific) + int(stated and (broad or specific)),
        "最も低い分野_類型内の位置%": field_rank[worst] / n * 100,
    })
res = pd.DataFrame(out)
res = res.sort_values(["満たす条件の数", "最も低い分野_類型内の位置%"], ascending=[False, True]).reset_index(drop=True)
res["判定"] = ["主ターゲット", "副ターゲット"] + ["対象外"] * (len(res) - 2)
save(res, "03_6市の判定.csv")
print(res.drop(columns=["総合計画メモ"]).round(2).to_string())
