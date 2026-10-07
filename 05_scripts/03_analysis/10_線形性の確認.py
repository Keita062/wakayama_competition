"""確認：Elastic Net回帰（線形モデル）を使ってよいか。ステップ3と改善候補①②の3か所のモデルで確かめる。

Elastic Netは「説明変数が1違うと目的変数が一定の幅だけ違う」という直線の関係を前提にする。関係が曲がっていたり、
変数の組み合わせで効き方が変わったりすると、説明力や係数を見誤るおそれがある。そこで次の2つで確かめる。
  1. LOWESS（局所的に重みをつけた回帰で描く滑らかな曲線）：各説明変数について、部分残差（目的変数から、ほかの変数の分を
     線形モデルの係数で引いたもの）とその変数の関係を描き、直線からどれだけ曲がっているかを見る。
     曲がりの大きさ＝（直線のあてはめの残差平方和 − LOWESSの残差平方和）÷ 目的変数の全平方和 ×100（ポイント）。
     曲線にすると目的変数の説明力が何ポイント増えるか、を表す（学習データでの値なので、多めに出る）。
  2. 交差検証R²の比較：線形モデルと同じ行・同じ分割（市町村単位の5分割、乱数5通り）・同じ重み（回答者数）で、
     非線形モデル2つの交差検証R²を出して比べる。
       - スプライン＋Elastic Net：各変数を3次スプライン（区切り4つ）で曲線に広げてからElastic Net。変数ごとの曲がりを取り込む
         （列が多いため、罰則の候補は alpha 30通り×l1_ratio 0.5・1.0 に絞る）
       - 勾配ブースティング（HistGradientBoosting）：決定木を積み重ねる。曲がりに加えて、変数の組み合わせの効き方も取り込む。
         設定（葉の数4・15）は交差検証R²の高いほうを使う（非線形に有利な選び方）
     差の95%信頼区間は、市町村を復元抽出するブートストラップ（2,000回、explain.lift_test と同じ方法）で出す。
判定：非線形モデルの上乗せの95%信頼区間の下限が0を超えなければ「線形で足りる」（曲線や組み合わせを入れても、
  学習に使っていない市町村の予測は偶然以上には良くならない）。
対象：
  - ステップ3：幸福度 ← 主観24分野（類型を揃えた全国・3類型。年代×性別×年度の行。04_ステップ3_寄与度.py と同じ前処理）
  - 改善候補①：重点分野の主観スコア ← 土台＋個別KPI（市町村×年度）
  - 改善候補②：重点分野の主観スコア ← 土台＋個別KPI＋追加の変数（市町村×年度）
出力：10_線形性_モデル比較.csv、10_線形性_曲がり.csv、06_figures/10_LOWESS_*.png
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score
from sklearn.preprocessing import SplineTransformer
from statsmodels.nonparametric.smoothers_lowess import lowess

from common import (BASE, KPIS, PROCESSED, SUBJ, TYPE_NAMES, TYPE_VARS, elastic_net, group_splits, load_focus, load_rows,
                    save, wmean)
from explain import base_design, build, zs

N_BOOT = 2000
SEEDS = range(5)
FIG = BASE / "06_figures"
plt.rcParams["font.family"] = ["Meiryo", "Yu Gothic", "MS Gothic"]
INK, INK2, GRID, SURF, BLUE, ORANGE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb", "#2a78d6", "#eb6834"


# ------------------------------------------------------------------ モデル
def spline(X, cont):
    """連続の列を3次スプライン（区切り4つ）に広げる。値の種類が少ない列とダミーはそのまま。"""
    parts = []
    for j in range(X.shape[1]):
        x = X[:, [j]]
        if j in cont and len(np.unique(x)) >= 10:
            lo, hi = np.percentile(x, [1, 99])
            parts.append(SplineTransformer(n_knots=4, degree=3, knots=np.linspace(lo, hi, 4)[:, None],
                                           extrapolation="linear").fit_transform(x))
        else:
            parts.append(x)
    S = np.hstack(parts)
    return (S - S.mean(0)) / np.where(S.std(0) > 0, S.std(0), 1)


def spline_cv(S, y, w, g):
    """スプライン＋Elastic Netの交差検証の予測。列が多く重いため、罰則の候補を絞る（alpha 30通り×l1_ratio 0.5・1.0、
    分割の乱数0で選ぶ）。テスト側の予測は線形と同じ乱数5通りの分割で出す。"""
    from sklearn.linear_model import ElasticNet, ElasticNetCV
    en = ElasticNetCV(l1_ratio=[0.5, 1.0], alphas=30, cv=group_splits(g, 0), max_iter=5000, tol=1e-3, n_jobs=-1)
    en.fit(S, y, sample_weight=w)
    preds = []
    for s in SEEDS:
        pred = np.zeros_like(y)
        for tr, te in group_splits(g, s):
            m = ElasticNet(alpha=en.alpha_, l1_ratio=en.l1_ratio_, max_iter=5000, tol=1e-3)
            pred[te] = m.fit(S[tr], y[tr], sample_weight=w[tr]).predict(S[te])
        preds.append(pred)
    return float(np.mean([r2_score(y, p, sample_weight=w) for p in preds])), np.mean(preds, axis=0)


def hgb_cv(X, y, w, g):
    """勾配ブースティングの交差検証の予測（葉の数4・15のうち交差検証R²の高いほう）。"""
    best = None
    for leaves in [4, 15]:
        preds = []
        for s in SEEDS:
            pred = np.zeros_like(y)
            for tr, te in group_splits(g, s):
                m = HistGradientBoostingRegressor(max_leaf_nodes=leaves, learning_rate=0.05, max_iter=300, min_samples_leaf=40,
                                                  l2_regularization=1.0, random_state=0)
                pred[te] = m.fit(X[tr], y[tr], sample_weight=w[tr]).predict(X[te])
            preds.append(pred)
        r2 = np.mean([r2_score(y, p, sample_weight=w) for p in preds])
        if best is None or r2 > best[0]:
            best = (r2, np.mean(preds, axis=0), leaves)
    return best


def boot_diff(y, w, g, p0, p1, seed=0):
    """交差検証R²の差（p1 − p0、ポイント）と、市町村単位のブートストラップによる95%信頼区間。"""
    uniq, inv = np.unique(g, return_inverse=True)
    agg = lambda v: np.bincount(inv, weights=v, minlength=len(uniq))
    sw, swy, swy2 = agg(w), agg(w * y), agg(w * y * y)
    se0, se1 = agg(w * (y - p0) ** 2), agg(w * (y - p1) ** 2)

    def diff(k):
        W, Y, Y2 = (k * sw).sum(), (k * swy).sum(), (k * swy2).sum()
        return ((k * se0).sum() - (k * se1).sum()) / (Y2 - Y * Y / W) * 100

    rng = np.random.default_rng(seed)
    boot = np.array([diff(np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))) for _ in range(N_BOOT)])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return diff(np.ones(len(uniq))), lo, hi


def curvature(X, y, w, coef, names, idx):
    """部分残差とLOWESSで、各変数の曲がりの大きさ（ポイント）を出す。戻り値：表と、図を描くための点と曲線。"""
    sst = np.sum(w * (y - np.average(y, weights=w)) ** 2)
    resid = y - X @ coef - np.average(y - X @ coef, weights=w)
    rows, curves = [], {}
    for j, name in zip(idx, names):
        x = X[:, j]
        pr = resid + coef[j] * x
        b = np.polyfit(x, pr, 1, w=np.sqrt(w))
        sse_lin = np.sum(w * (pr - np.polyval(b, x)) ** 2)
        fit = lowess(pr, x, frac=0.5, it=0, delta=0.01 * np.ptp(x), return_sorted=False)
        sse_lo = np.sum(w * (pr - fit) ** 2)
        rows.append((name, coef[j], (sse_lin - sse_lo) / sst * 100))
        o = np.argsort(x)
        curves[name] = (x, pr, x[o], fit[o], b)
    return pd.DataFrame(rows, columns=["変数", "線形の係数", "曲がりの大きさ"]), curves


def compare(label, X, y, w, g, cont, names, idx):
    """線形・スプライン・勾配ブースティングの交差検証R²と、線形に対する上乗せ（95%信頼区間）。"""
    en, r_lin, p_lin = elastic_net(X, y, w, g)
    print(label, "線形", round(r_lin, 3), flush=True)
    r_spl, p_spl = spline_cv(spline(X, cont), y, w, g)
    print(label, "スプライン", round(r_spl, 3), flush=True)
    r_hgb, p_hgb, leaves = hgb_cv(X, y, w, g)
    print(label, "勾配ブースティング", round(r_hgb, 3), flush=True)
    out = [(label, "線形（Elastic Net）", len(y), len(np.unique(g)), r_lin * 100, np.nan, np.nan, np.nan, "")]
    for name, r2, p, note in [("スプライン＋Elastic Net", r_spl, p_spl, "変数ごとの曲がり"),
                              ("勾配ブースティング", r_hgb, p_hgb, f"曲がり＋組み合わせ（葉の数{leaves}）")]:
        d, lo, hi = boot_diff(y, w, g, p_lin, p)
        out.append((label, name, len(y), len(np.unique(g)), r2 * 100, d, lo, hi, note))
    cur, curves = curvature(X, y, w, en.coef_, names, idx)
    cur.insert(0, "モデル", label)
    print(label, [round(o[4], 2) for o in out], [round(o[5], 2) for o in out[1:]])
    return out, cur, curves


def draw(curves, cur, fname, ylabel, ncol=4):
    """変数ごとの部分残差（点）、LOWESS（オレンジ）、直線（青）。"""
    names = list(cur.sort_values("曲がりの大きさ", ascending=False)["変数"])
    nrow = int(np.ceil(len(names) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.0 * ncol, 2.4 * nrow), dpi=130, squeeze=False)
    fig.patch.set_facecolor(SURF)
    rng = np.random.default_rng(0)
    for ax, name in zip(axes.flat, names):
        x, pr, xs, fit, b = curves[name]
        k = rng.choice(len(x), min(len(x), 3000), replace=False)
        lo, hi = np.percentile(x, [0.5, 99.5])
        ax.set_facecolor(SURF)
        ax.scatter(x[k], pr[k], s=3, color="#c9c8c3", alpha=0.5, linewidths=0)
        ax.plot([lo, hi], np.polyval(b, [lo, hi]), color=BLUE, linewidth=1.6)
        m = (xs >= lo) & (xs <= hi)
        ax.plot(xs[m], fit[m], color=ORANGE, linewidth=1.8)
        ax.set_xlim(lo, hi)
        yl = np.percentile(pr, [1, 99])
        ax.set_ylim(yl[0] - 0.1 * np.ptp(yl), yl[1] + 0.1 * np.ptp(yl))
        c = cur.set_index("変数").loc[name, "曲がりの大きさ"]
        ax.set_title(f"{name}\n曲がり {c:.2f}pt", fontsize=8, color=INK)
        ax.tick_params(colors=INK2, labelsize=7, length=0)
        for s in ax.spines.values():
            s.set_color(GRID)
    for ax in list(axes.flat)[len(names):]:
        ax.axis("off")
    fig.supxlabel("説明変数（標準化した値）", fontsize=9, color=INK2)
    fig.supylabel(ylabel, fontsize=9, color=INK2)
    fig.tight_layout()
    fig.savefig(FIG / fname, facecolor=SURF)
    plt.close(fig)


# ------------------------------------------------------------------ ステップ3：幸福度 ← 主観24分野
def demean(df, cols, keys):
    out = df[cols].copy()
    for c in cols:
        gm = df.groupby(keys).apply(lambda q: wmean(q[c], q["回答者数"]), include_groups=False)
        out[c] = df[c] - df.set_index(keys).index.map(gm).values
    return out


def standardize(a, w):
    m = np.average(a, axis=0, weights=w)
    return (a - m) / np.sqrt(np.average((a - m) ** 2, axis=0, weights=w))


rows = load_rows()
fields = [s.removeprefix("主観_") for s in SUBJ]
models, curs = [], []
for label, df in [("類型を揃えた全国", rows)] + [(t, rows[rows["類型"] == t]) for t in TYPE_NAMES]:
    df = df.reset_index(drop=True)
    d = demean(df, ["幸福度"] + SUBJ, ["類型", "年度", "年代", "性別"])
    w = df["回答者数"].values.astype(float)
    y, X = standardize(d[["幸福度"]].values, w)[:, 0], standardize(d[SUBJ].values, w)
    out, cur, curves = compare(f"ステップ3（{label}）", X, y, w, df["市区町村コード"].values, set(range(24)), fields, range(24))
    models += out
    curs.append(cur)
    if label == "類型を揃えた全国":
        draw(curves, cur, "10_LOWESS_ステップ3.png", "幸福度の部分残差（標準化）", ncol=6)

# ------------------------------------------------------------------ 改善候補①②：重点分野の主観スコア ← 土台＋変数
extra = pd.read_csv(PROCESSED / "03_追加変数.csv", dtype={"市区町村コード": str})
defs = pd.read_csv(PROCESSED / "03_追加変数_定義.csv").set_index("列名")
focus = load_focus()
for field in dict.fromkeys(focus.values()):
    city = "・".join(c for c, f in focus.items() if f == field)
    kcols = [c for c, (f, _, _) in KPIS.items() if f == field]
    xcols = defs.index[defs["分野"] == field].tolist()
    for step, cols, ex in [("改善候補①", kcols, None), ("改善候補②", kcols + xcols, extra)]:
        d = build(field, cols, ex).dropna(subset=["主観スコア"] + TYPE_VARS + cols).reset_index(drop=True)
        B = base_design(d)
        Xdf = pd.concat([B, d[cols]], axis=1)
        X = zs(Xdf).values
        cont = {Xdf.columns.get_loc(c) for c in TYPE_VARS + cols}
        names = [KPIS[c][2] if c in KPIS else defs.loc[c, "表示名"] for c in cols]
        idx = [Xdf.columns.get_loc(c) for c in cols]
        out, cur, curves = compare(f"{step}（{city}×{field}）", X, d["主観スコア"].values, d["回答者数"].values.astype(float),
                                   d["市区町村コード"].values, cont, names, idx)
        models += out
        curs.append(cur)
        if step == "改善候補②":
            draw(curves, cur, f"10_LOWESS_{city}_{field}.png", f"{field}の主観スコアの部分残差", ncol=5)

m = pd.DataFrame(models, columns=["モデル", "比べたモデル", "行数", "市町村数", "交差検証R2%", "線形に対する上乗せ", "上乗せ_下限95",
                                  "上乗せ_上限95", "取り込むもの"])
m["判定"] = np.where(m["比べたモデル"].str.startswith("線形"), "",
                    np.where(m["上乗せ_下限95"] > 0, "非線形のほうが良い", "線形で足りる"))
save(m, "10_線形性_モデル比較.csv")
save(pd.concat(curs), "10_線形性_曲がり.csv")
print(m.round(2).to_string(index=False))
