"""ステップ3：幸福度を主観24分野で説明する重回帰（Elastic Net回帰）から、各分野の説明力（重要度）を出す。

各行（市町村×年度×年代×性別）の幸福度と主観24分野から、同じ「類型×年度×年代×性別」の平均（回答者数で重みづけ）を引き、
平均0・ばらつき1に標準化してから、幸福度を主観24分野でElastic Net回帰する（回答者数で重みづけ）。
  - 正則化の強さ（alpha）とL1の割合（l1_ratio）は、市町村単位で分けた5分割交差検証（GroupKFold）で選ぶ
    （同じ市町村の別年度・別の年代×性別が、学習とテストにまたがらないようにする）
  - 重要度＝標準化偏回帰係数の絶対値。全分野の合計を100%とした割合を「説明力の取り分」とする
  - 確認：通常の重回帰の説明力R²を分け合う相対重要度分析（LMG、足す順番1,500通り）も出し、Elastic Netの重要度との順位相関を見る
全国（類型をそろえた）・都市部・地方の中心都市・農山村の小都市で計算。
出力：04_寄与度.csv、04_モデル.csv
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import ElasticNet, ElasticNetCV
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold

from common import FIELDS, SUBJ, TYPE_NAMES, load_rows, save, wmean

N_PERM = 1500
L1_RATIOS = [0.1, 0.3, 0.5, 0.7, 0.9, 0.95, 1.0]
rng = np.random.default_rng(0)


def demean(df, cols, keys):
    out = df[cols].copy()
    for c in cols:
        gm = df.groupby(keys).apply(lambda g: wmean(g[c], g["回答者数"]), include_groups=False)
        out[c] = df[c] - df.set_index(keys).index.map(gm).values
    return out


def standardize(a, w):
    m = np.average(a, axis=0, weights=w)
    sd = np.sqrt(np.average((a - m) ** 2, axis=0, weights=w))
    return (a - m) / sd


def elastic_net(y, X, w, groups):
    splits = list(GroupKFold(n_splits=5).split(X, y, groups))
    en = ElasticNetCV(l1_ratio=L1_RATIOS, alphas=100, cv=splits, max_iter=20000, n_jobs=-1)
    en.fit(X, y, sample_weight=w)
    # 選ばれたalpha・l1_ratioで、分割ごとに学習し直してテスト側の説明力を出す（交差検証R²）
    pred = np.zeros_like(y)
    for tr, te in splits:
        m = ElasticNet(alpha=en.alpha_, l1_ratio=en.l1_ratio_, max_iter=20000).fit(X[tr], y[tr], sample_weight=w[tr])
        pred[te] = m.predict(X[te])
    cv_r2 = r2_score(y, pred, sample_weight=w)
    r2 = r2_score(y, en.predict(X), sample_weight=w)
    return en, r2, cv_r2


def r2_func(y, X, w):
    """重みつき最小二乗のR²を、説明変数の部分集合ごとにすばやく出す（正規方程式）。"""
    sw = np.sqrt(w)
    yw, Xw = y * sw, X * sw[:, None]
    tss = np.sum(yw ** 2)  # 平均を引いてあるので切片なし
    G, b = Xw.T @ Xw, Xw.T @ yw

    def r2(idx):
        if not idx:
            return 0.0
        idx = list(idx)
        beta = np.linalg.solve(G[np.ix_(idx, idx)], b[idx])
        return float(beta @ b[idx]) / tss
    return r2


def lmg(y, X, w):
    r2 = r2_func(y, X, w)
    total = r2(range(X.shape[1]))
    share = np.zeros(X.shape[1])
    for _ in range(N_PERM):
        prev, used = 0.0, []
        for j in rng.permutation(X.shape[1]):
            used.append(j)
            cur = r2(used)
            share[j] += cur - prev
            prev = cur
    return share / N_PERM / total


rows = load_rows()
out, models = [], []
for label, df in [("類型を揃えた全国", rows)] + [(t, rows[rows["類型"] == t]) for t in TYPE_NAMES]:
    df = df.reset_index(drop=True)
    d = demean(df, ["幸福度"] + SUBJ, ["類型", "年度", "年代", "性別"])
    w = df["回答者数"].values.astype(float)
    y, X = standardize(d[["幸福度"]].values, w)[:, 0], standardize(d[SUBJ].values, w)
    en, r2, cv_r2 = elastic_net(y, X, w, df["市区町村コード"].values)
    imp = np.abs(en.coef_) / np.abs(en.coef_).sum()
    share = lmg(y, X, w)
    rho = spearmanr(imp, share).statistic
    models.append((label, len(df), r2, cv_r2, en.alpha_, en.l1_ratio_, int((en.coef_ != 0).sum()), rho))
    v = d[["幸福度"] + SUBJ].values
    sd = np.sqrt(np.average((v - np.average(v, axis=0, weights=w)) ** 2, axis=0, weights=w))
    pts = en.coef_ * sd[0] / sd[1:]  # 主観スコアが1点上がると幸福度（0〜10点）が何点上がるか
    rank = pd.Series(imp).rank(ascending=False, method="min").astype(int).values
    lrank = pd.Series(share).rank(ascending=False, method="min").astype(int).values
    for f, c, pt, s, r, ls, lr in zip(FIELDS, en.coef_, pts, imp, rank, share, lrank):
        out.append((label, len(df), f, c, pt, s * 100, r, ls * 100, lr))
    print(label, len(df), "R2", round(r2, 3), "CV R2", round(cv_r2, 3), "alpha", round(en.alpha_, 4), "l1", en.l1_ratio_, "rho", round(rho, 2))
res = pd.DataFrame(out, columns=["対象", "行数", "分野", "標準化係数", "係数_主観スコア1点あたり", "取り分%", "順位", "LMG取り分%", "LMG順位"])
mod = pd.DataFrame(models, columns=["対象", "行数", "説明力R2", "交差検証R2", "alpha", "l1_ratio", "係数が0でない分野数", "LMGとの順位相関"])
save(res, "04_寄与度.csv")
save(mod, "04_モデル.csv")
print(res.pivot_table(index="分野", columns="対象", values="取り分%").sort_values("類型を揃えた全国", ascending=False).round(1).head(12).to_string())
