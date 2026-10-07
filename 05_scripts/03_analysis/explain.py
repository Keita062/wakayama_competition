"""改善候補①・②共通：重点分野の主観スコアを、変数（個別KPI・追加の変数）でどれだけ説明できるかをElastic Net回帰で調べる。

データ：市町村×年度版（2023〜26）。1行＝1市町村の1年度。
  - 目的変数：その分野の主観スコア（年代×性別の構成をそろえた主観スコア。市町村×年度ごと）
  - 説明変数：年度ごとに値があるものは、その年度版に対応する年（Y−1年）の値。1時点しかないものは同じ値をどの年度にも使う
  - 重み：その市町村・年度の回答者数
回帰（Elastic Net回帰、common.elastic_net）：
  1. 説明変数をすべて平均0・ばらつき1に標準化する（係数＝その変数が1標準偏差違うと主観スコアが何点違うか）
  2. L1（Lasso）とL2（Ridge）の罰則を組み合わせて係数を縮める。似た動きをする変数同士（多重共線性）があっても係数が暴れにくく、
     効かない変数の係数は0になる
  3. 罰則の強さ（alpha）とL1の割合（l1_ratio：0.1〜1.0の7通り）は、市町村単位の5分割交差検証（GroupKFold）で選ぶ。
     同じ市町村の別の年度が学習とテストにまたがると説明力を高く見積もってしまうため、市町村ごとに分ける
  4. 説明力は交差検証R²で測る（分割の乱数5通りでテスト側の予測を出して平均し、その予測の当てはまりを見る）
説明できるかの判定（lift_test）：土台と、変数を加えたモデルの、テスト側の予測（同じ行・同じ分割）を比べる。
  市町村を復元抽出するブートストラップ（2,000回）で交差検証R²の上乗せの95%信頼区間を出し、下限が0を超えれば
  「説明できる」（変数を加えると、学習に使っていない市町村の主観スコアの予測が偶然では説明できないほど良くなる）とする。
  上乗せの大きさに恣意的な閾値を置かず、予測精度の差の検定（入れ子のモデルを交差検証の予測誤差で比べる）で判定する。
効いた変数：市町村単位のブートストラップ（市町村を復元抽出して200回学習し直す）で、想定どおりの向きの係数が出た割合が90%以上のもの。
"""
import numpy as np
import pandas as pd

from common import (TIME_VARYING, TYPE_VARS, city_values, elastic_net, load_kpi, load_panel, load_rows, stability)

N_BOOT = 2000  # 上乗せの信頼区間を出すブートストラップの回数
STABLE = 0.9  # 効いたとみなす、想定どおりの向きの割合


def build(field, cols, extra=None):
    """市町村×年度の表：主観スコア・回答者数・土台の変数・指定した列（個別KPI、追加の変数）。
    extra：追加の変数の表（市区町村コード・年度版・変数）。"""
    rows = load_rows()
    subj = f"主観_{field}"
    y = city_values(rows, [subj], by=("市区町村コード", "年度"))[subj].rename("主観スコア")
    n = rows.groupby(["市区町村コード", "年度"])["回答者数"].sum().rename("回答者数")
    d = pd.concat([y, n], axis=1).reset_index()
    info = rows.drop_duplicates("市区町村コード").set_index("市区町村コード")[["都道府県", "市区町村", "類型"]]
    d = d.join(info, on="市区町村コード")
    static = load_kpi().set_index("市区町村コード")
    panel = load_panel().rename(columns={"年度版": "年度"})
    ex = extra.rename(columns={"年度版": "年度"}) if extra is not None else None
    for c in TYPE_VARS + cols:
        if c in d:
            continue
        if ex is not None and c in ex:
            d = d.merge(ex[["市区町村コード", "年度", c]], on=["市区町村コード", "年度"], how="left")
        elif c in TIME_VARYING:
            d = d.merge(panel[["市区町村コード", "年度", c]], on=["市区町村コード", "年度"], how="left")
        else:
            d[c] = d["市区町村コード"].map(static[c])
    d["人口"], d["人口密度"] = np.log(d["人口"]), np.log(d["人口密度"])
    return d


def base_design(d):
    """土台：類型（ダミー）＋類型の6変数（人口・人口密度は対数）＋年度（ダミー）。"""
    return pd.concat([pd.get_dummies(d["類型"], drop_first=True), pd.get_dummies(d["年度"], prefix="年度", drop_first=True),
                      d[TYPE_VARS]], axis=1).astype(float)


def zs(X):
    return (X - X.mean()) / X.std()


def fit(d, cols, signs):
    """土台＋cols のElastic Net。戻り値：交差検証R²、モデル、係数の表、予測。cols が空なら土台だけ。"""
    X = pd.concat([base_design(d), d[cols]], axis=1)
    y, w, g = d["主観スコア"].values, d["回答者数"].values, d["市区町村コード"].values
    en, r2, oof = elastic_net(zs(X).values, y, w, g)
    coef = pd.DataFrame()
    if cols:
        pos, neg = stability(zs(X).values, y, w, g, en.alpha_, en.l1_ratio_)
        j = [list(X.columns).index(c) for c in cols]
        sd = d[cols].std()
        coef = pd.DataFrame({"列名": cols, "望ましい向き": [signs[c] for c in cols],
                             "係数_1SD": en.coef_[j], "係数_1単位": en.coef_[j] / sd.values,
                             "想定どおりの向きの割合": [(pos if signs[c] > 0 else neg)[i] for c, i in zip(cols, j)]})
        coef["効いた"] = coef["想定どおりの向きの割合"] >= STABLE
    pred = d[["市区町村コード", "都道府県", "市区町村", "類型", "年度", "主観スコア"]].copy()
    pred["予測"] = en.predict(zs(X).values)
    pred["交差検証の予測"] = oof
    return r2, en, coef, pred


def lift_test(d, pred0, pred1, seed=0):
    """土台（pred0）に対する拡張モデル（pred1）の交差検証R²の上乗せと、市町村単位のブートストラップによる95%信頼区間。
    戻り値：上乗せ（ポイント）、下限、上限、上乗せが0以下になった割合（片側p値に相当）、土台と拡張モデルの交差検証R²（%）。"""
    y, w = d["主観スコア"].values, d["回答者数"].values.astype(float)
    e0, e1 = (y - pred0["交差検証の予測"].values) ** 2, (y - pred1["交差検証の予測"].values) ** 2
    codes = d["市区町村コード"].values
    uniq, inv = np.unique(codes, return_inverse=True)
    # 市町村ごとに集計しておき、復元抽出は市町村の重複回数で重みづけて計算する
    agg = lambda v: np.bincount(inv, weights=v, minlength=len(uniq))
    sw, swy, swy2, se0, se1 = agg(w), agg(w * y), agg(w * y * y), agg(w * e0), agg(w * e1)

    def sst(k):
        W, Y, Y2 = (k * sw).sum(), (k * swy).sum(), (k * swy2).sum()
        return Y2 - Y * Y / W

    def lift(k):
        return ((k * se0).sum() - (k * se1).sum()) / sst(k) * 100

    est = lift(np.ones(len(uniq)))
    rng = np.random.default_rng(seed)
    boot = np.array([lift(np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))) for _ in range(N_BOOT)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    one = np.ones(len(uniq))
    r0, r1 = (1 - se0.sum() / sst(one)) * 100, (1 - se1.sum() / sst(one)) * 100
    return est, lo, hi, float((boot <= 0).mean()), r0, r1
