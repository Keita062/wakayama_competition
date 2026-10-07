"""分析スクリプト共通：パス、分析対象行の読み込み、年代×性別の構成をそろえた市町村値、個別KPIの定義。

各ステップのスクリプト（NN_*.py）は 04_data/03_analysis/NN_*.csv に結果を書き、
10_レポート作成.py がそれを読んで 01_docs/ にMarkdownのレポートを作る。
"""
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
CONTEXT = BASE / "00_context"
PROCESSED = BASE / "04_data" / "02_processed"
OUT = BASE / "04_data" / "03_analysis"
DOCS = BASE / "01_docs"
OUT.mkdir(parents=True, exist_ok=True)

WB_XLSX = CONTEXT / "地域幸福度_市区町村別データ_2022-2026.xlsx"
KPI_CSV = PROCESSED / "01_市区町村別_個別KPI.csv"

FIELDS = ["医療・福祉", "買物・飲食", "住宅環境", "移動・交通", "遊び・娯楽", "子育て", "初等・中等教育", "地域行政",
          "デジタル生活", "公共空間", "都市景観", "事故・犯罪", "自然景観", "自然の恵み", "環境共生", "自然災害",
          "地域とのつながり", "多様性と寛容性", "自己効力感", "健康状態", "文化・芸術", "教育機会の豊かさ", "雇用・所得", "事業創造"]
SUBJ = [f"主観_{f}" for f in FIELDS]
OBJ = [f"客観_{f}" for f in FIELDS]

TYPE_VARS = ["人口", "人口密度", "高齢化率", "財政力指数", "第1次産業就業者割合", "可住地面積割合"]
TYPE_NAMES = ["都市部", "地方の中心都市", "農山村の小都市"]  # 人口密度の中央値が高い順
WAKAYAMA6 = ["和歌山市", "海南市", "橋本市", "田辺市", "紀の川市", "岩出市"]
KINKI = ["滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"]

# 個別KPI：列名 → (分野, 望ましい向き +1/-1, 表示名)
KPIS = {
    "商業施設徒歩圏人口カバー率": ("買物・飲食", +1, "商業施設徒歩圏人口カバー率"),
    "可住地面積あたり飲食店数": ("買物・飲食", +1, "可住地面積あたり飲食店数"),
    "駅バス停徒歩圏人口カバー率": ("移動・交通", +1, "駅・バス停徒歩圏人口カバー率"),
    "人口あたり小型車走行キロ": ("移動・交通", -1, "人口あたり小型車走行キロ"),
    "医療施設徒歩圏人口カバー率": ("医療・福祉", +1, "医療施設徒歩圏人口カバー率"),
    "福祉施設徒歩圏人口カバー率": ("医療・福祉", +1, "福祉施設徒歩圏人口カバー率"),
    "公園緑地徒歩圏人口カバー率": ("公共空間", +1, "公園緑地徒歩圏人口カバー率"),
    "ウォーカブル推進都市": ("公共空間", +1, "ウォーカブル推進都市"),
    "人口あたり公園面積": ("公共空間", +1, "人口あたり公園面積"),
    "歩道設置率": ("公共空間", +1, "歩道設置率"),
    "既婚者割合": ("地域とのつながり", +1, "既婚者割合"),
    "高齢単身世帯割合": ("地域とのつながり", -1, "高齢単身世帯割合"),
    "人口あたり宗教の事業所数": ("地域とのつながり", +1, "人口あたり宗教の事業所数"),
    "人口あたりNPOの数": ("地域とのつながり", +1, "人口あたりNPOの数"),
    "人口あたり自殺者数": ("地域とのつながり", -1, "人口あたり自殺者数"),
    "拡大家族世帯割合": ("地域とのつながり", +1, "拡大家族世帯割合"),
    "可住地面積あたり幼稚園数": ("子育て", +1, "可住地面積あたり幼稚園数"),
    "歳出総額の教育費割合": ("子育て", +1, "歳出総額の教育費割合"),
    "保育所徒歩圏0_4歳人口カバー率": ("子育て", +1, "保育所徒歩圏0〜4歳人口カバー率"),
    "可住地面積あたり高等学校数": ("初等・中等教育", +1, "可住地面積あたり高等学校数"),
    "健康寿命_女性_近似": ("健康状態", +1, "健康寿命（女性・近似）"),
    "健康寿命_男性_近似": ("健康状態", +1, "健康寿命（男性・近似）"),
    "転入超過割合": ("自己効力感", +1, "転入超過割合"),
    "完全失業者数_人口比": ("自己効力感", -1, "完全失業者数（人口比）"),
    "完全失業率": ("雇用・所得", -1, "完全失業率"),
    "一戸建の持ち家の割合": ("住宅環境", +1, "一戸建の持ち家の割合"),
    "住宅当たり延べ面積": ("住宅環境", +1, "住宅当たり延べ面積"),
    "実質公債費比率": ("地域行政", -1, "実質公債費比率"),
}
# 施策で動かせるか：列名 → (区分, 理由)
#   動かせる：市の施策（施設・路線・予算・制度・支援など）で値を変えられる
#   動かせない：人口構造・家族構成・健康や生活の結果で、市の施策では変えにくい（伸ばす数値の対象外）
#   どれくらいの期間で動かせるかは、伸ばす数値が決まった後の施策の検討で扱う
CONTROL = {
    "商業施設徒歩圏人口カバー率": ("動かせる", "立地誘導で動くが、出店は民間の判断"),
    "可住地面積あたり飲食店数": ("動かせる", "出店は民間の判断"),
    "駅バス停徒歩圏人口カバー率": ("動かせる", "バス路線・停留所の配置、デマンド交通で動かせる"),
    "人口あたり小型車走行キロ": ("動かせない", "暮らし方の結果"),
    "医療施設徒歩圏人口カバー率": ("動かせる", "診療所の立地は民間の判断"),
    "福祉施設徒歩圏人口カバー率": ("動かせる", "施設整備には計画と年数が要る"),
    "公園緑地徒歩圏人口カバー率": ("動かせる", "用地の確保に年数が要る"),
    "ウォーカブル推進都市": ("動かせる", "国への賛同の表明で該当する"),
    "人口あたり公園面積": ("動かせる", "用地の確保に年数が要る"),
    "歩道設置率": ("動かせる", "道路改良に年数が要る"),
    "既婚者割合": ("動かせない", "人口構造・個人の選択の結果"),
    "高齢単身世帯割合": ("動かせない", "人口構造・家族構成の結果"),
    "人口あたり宗教の事業所数": ("動かせない", "市の施策の対象外"),
    "人口あたりNPOの数": ("動かせる", "設立・活動の支援で動かせる"),
    "人口あたり自殺者数": ("動かせない", "多くの要因が重なった結果の指標"),
    "拡大家族世帯割合": ("動かせない", "家族構成の結果"),
    "可住地面積あたり幼稚園数": ("動かせる", "少子化で新設は難しい"),
    "歳出総額の教育費割合": ("動かせる", "予算配分で動かせる"),
    "保育所徒歩圏0_4歳人口カバー率": ("動かせる", "施設整備に年数が要る"),
    "可住地面積あたり高等学校数": ("動かせない", "高校の設置は主に県"),
    "健康寿命_女性_近似": ("動かせない", "高齢者の健康の積み重ねの結果で、施策の効果が出るまで長い"),
    "健康寿命_男性_近似": ("動かせない", "高齢者の健康の積み重ねの結果で、施策の効果が出るまで長い"),
    "転入超過割合": ("動かせない", "雇用・住宅・教育など多くの要因の結果"),
    "完全失業者数_人口比": ("動かせる", "雇用の場づくり・就労支援で間接に動く"),
    "完全失業率": ("動かせる", "雇用の場づくり・就労支援で間接に動く"),
    "一戸建の持ち家の割合": ("動かせない", "住宅ストックの結果"),
    "住宅当たり延べ面積": ("動かせない", "住宅ストックの結果"),
    "実質公債費比率": ("動かせる", "過去の借入の返済で決まる"),
    # 追加の変数（改善候補②）
    "居住期間20年以上割合": ("動かせない", "人の出入りの結果"),
    "共同住宅世帯割合": ("動かせない", "住宅ストックの結果"),
    "昼夜間人口比率": ("動かせない", "通勤・通学の流れの結果"),
    "他市区町村への通勤者割合": ("動かせない", "通勤の流れの結果"),
    "人口あたり政治経済文化団体の事業所数": ("動かせない", "市の施策の対象外"),
    "人口あたり公民館数": ("動かせる", "施設の新設・転用には計画と年数が要る"),
    "人口あたり図書館数": ("動かせる", "施設の新設には計画と年数が要る"),
    "人口あたり社会体育施設数": ("動かせる", "施設の新設には計画と年数が要る"),
    "人口あたり集会施設数": ("動かせる", "施設の新設・転用には計画と年数が要る"),
    "高齢者千人あたり通いの場の箇所数": ("動かせる", "住民主体の通いの場の立ち上げ支援（介護予防事業）で動かせる"),
    "通いの場の参加率": ("動かせる", "通いの場の立ち上げ・参加の呼びかけで動かせる"),
    "人口あたり地域おこし協力隊員数": ("動かせる", "隊員の募集・受け入れで動かせる"),
    "就業率": ("動かせる", "雇用の場づくり・就労支援で間接に動く"),
    "女性就業率": ("動かせる", "保育・就労支援で間接に動く"),
    "65歳以上就業率": ("動かせる", "シルバー人材センター・就労支援で間接に動く"),
    "正規雇用割合": ("動かせる", "企業誘致・雇用支援で間接に動く"),
    "大学卒業者割合": ("動かせない", "学歴構成の結果"),
    "納税義務者1人あたり課税対象所得": ("動かせる", "産業振興で間接に動く"),
    "20_39歳人口割合": ("動かせない", "人口構造の結果"),
    "20_39歳転入超過率": ("動かせない", "雇用・住宅・教育など多くの要因の結果"),
    "人口あたり新設事業所数": ("動かせる", "創業支援で間接に動く"),
    "新設事業所割合": ("動かせる", "創業支援で間接に動く"),
}


def load_focus():
    """ステップ4で決めた重点分野：市 → 分野。"""
    m = pd.read_csv(OUT / "05_重点分野マトリクス.csv")
    return m[m["重点分野"]].set_index("市")["分野"].to_dict()


# 改善候補①で見る13分野（PDFの表の順）
KPI_FIELDS = ["買物・飲食", "地域とのつながり", "移動・交通", "医療・福祉", "公共空間", "子育て", "初等・中等教育",
              "健康状態", "自己効力感", "雇用・所得", "住宅環境", "地域行政", "遊び・娯楽"]


def wmean(x, w):
    x, w = np.asarray(x, float), np.asarray(w, float)
    m = ~np.isnan(x)
    return np.sum(x[m] * w[m]) / np.sum(w[m]) if m.any() else np.nan


def load_wb():
    """全国版ウェルビーイングデータ（主観・客観）。初回だけExcelを読み、pickleにキャッシュする。"""
    cache = OUT / "_cache_wb.pkl"
    if cache.exists() and cache.stat().st_mtime > WB_XLSX.stat().st_mtime:
        return pd.read_pickle(cache)
    s = pd.read_excel(WB_XLSX, sheet_name="主観データ")
    o = pd.read_excel(WB_XLSX, sheet_name="客観データ")
    pd.to_pickle((s, o), cache)
    return s, o


PANEL_CSV = PROCESSED / "02_市区町村別_個別KPI_年度別_横.csv"
SURVEY_YEARS = [2023, 2024, 2025, 2026]


def load_panel():
    """年度ごとに値がある個別KPI（市区町村コード×年度版）。年度版Yには Y−1年の値が入っている。"""
    return pd.read_csv(PANEL_CSV, dtype={"市区町村コード": str})


def load_kpi():
    """市町村ごとの個別KPI・類型変数。年度ごとに値があるものは、調査の年度版2023〜26に対応する年の平均で置き換える。"""
    k = pd.read_csv(KPI_CSV, dtype={"市区町村コード": str}).set_index("市区町村コード")
    p = load_panel()
    m = p[p["年度版"].isin(SURVEY_YEARS)].groupby("市区町村コード").mean(numeric_only=True).drop(columns="年度版")
    for c in m.columns:
        k[c] = m[c].reindex(k.index)
    return k.reset_index()


TIME_VARYING = [c for c in pd.read_csv(PANEL_CSV, nrows=1).columns if c not in ("市区町村コード", "年度版")] if PANEL_CSV.exists() else []


L1_RATIOS = [0.1, 0.3, 0.5, 0.7, 0.9, 0.95, 1.0]


def group_splits(groups, seed, k=5):
    """市町村単位のk分割（同じ市町村の別年度が学習とテストにまたがらないようにする）。"""
    from sklearn.model_selection import GroupKFold
    return list(GroupKFold(n_splits=k, shuffle=True, random_state=seed).split(np.zeros(len(groups)), groups=groups))


def elastic_net(X, y, w, groups, seeds=range(5)):
    """Elastic Net回帰（説明変数は平均0・ばらつき1に標準化済み、回答者数で重みづけ）。
    alphaとl1_ratioは市町村単位の5分割交差検証で選び、選んだ値で分割ごとに学習し直したテスト側の説明力（交差検証R²）を
    乱数5通りで平均する。戻り値：全データで学習したモデル、交差検証R²、テスト側の予測（乱数5通りの平均）。"""
    from sklearn.linear_model import ElasticNet, ElasticNetCV
    from sklearn.metrics import r2_score
    X, y, w = np.asarray(X, float), np.asarray(y, float), np.asarray(w, float)
    en = ElasticNetCV(l1_ratio=L1_RATIOS, alphas=100, cv=group_splits(groups, 0), max_iter=50000, n_jobs=-1)
    en.fit(X, y, sample_weight=w)
    r2s, preds = [], []
    for s in seeds:
        pred = np.zeros_like(y)
        for tr, te in group_splits(groups, s):
            m = ElasticNet(alpha=en.alpha_, l1_ratio=en.l1_ratio_, max_iter=50000).fit(X[tr], y[tr], sample_weight=w[tr])
            pred[te] = m.predict(X[te])
        r2s.append(r2_score(y, pred, sample_weight=w))
        preds.append(pred)
    return en, float(np.mean(r2s)), np.mean(preds, axis=0)


def stability(X, y, w, groups, alpha, l1_ratio, n_boot=200, seed=0):
    """市町村単位のブートストラップ（市町村を復元抽出して学習し直す）で、係数の向きがどれだけ安定するかを見る。
    戻り値：各説明変数の「係数がプラスだった割合」「マイナスだった割合」。"""
    from sklearn.linear_model import ElasticNet
    X, y, w, groups = np.asarray(X, float), np.asarray(y, float), np.asarray(w, float), np.asarray(groups)
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    idx_of = {g: np.flatnonzero(groups == g) for g in uniq}
    pos, neg = np.zeros(X.shape[1]), np.zeros(X.shape[1])
    for _ in range(n_boot):
        idx = np.concatenate([idx_of[g] for g in rng.choice(uniq, len(uniq), replace=True)])
        c = ElasticNet(alpha=alpha, l1_ratio=l1_ratio, max_iter=50000).fit(X[idx], y[idx], sample_weight=w[idx]).coef_
        pos += c > 0
        neg += c < 0
    return pos / n_boot, neg / n_boot


def with_name(df):
    """ウェルビーイングデータの地域名を個別KPI表の市区町村名にそろえる（政令市の「全域」を外す）。"""
    df = df.copy()
    df["name"] = df["市区町村"].str.replace("全域$", "", regex=True)
    return df


def load_rows():
    """00_前処理.py が作った分析対象行（年代×性別、17,609行）と類型を読み込む。"""
    rows = pd.read_csv(OUT / "00_分析対象行.csv", dtype={"市区町村コード": str})
    typ = OUT / "01_類型.csv"
    if typ.exists():
        t = pd.read_csv(typ, dtype={"市区町村コード": str})[["市区町村コード", "類型"]]
        rows = rows.merge(t, on="市区町村コード", how="left")
    return rows


def adjust(rows, cols, keys=("年度", "年代", "性別")):
    """年代×性別（×年度）の構成をそろえる：各行から、同じ keys の全国平均（回答者数で重みづけ）を引く。"""
    keys = list(keys)
    out = rows.copy()
    for c in cols:
        gm = rows.groupby(keys).apply(lambda g: wmean(g[c], g["回答者数"]), include_groups=False)
        out[c] = rows[c] - rows.set_index(keys).index.map(gm).values
    return out


def city_values(rows, cols, by=("市区町村コード",), keys=("年度", "年代", "性別")):
    """市町村ごとの「年代×性別の構成をそろえた値」：調整後の残差を回答者数で重みづけして平均し、全体平均を足し戻す。"""
    adj = adjust(rows, cols, keys)
    res = {}
    for c in cols:
        overall = wmean(rows[c], rows["回答者数"])
        res[c] = adj.groupby(list(by)).apply(lambda g: wmean(g[c], g["回答者数"]), include_groups=False) + overall
    return pd.DataFrame(res)


def pct_rank(s, ascending=True):
    """低いほうから数えた位置（0〜100のパーセンタイル）。"""
    r = s.rank(ascending=ascending, method="average")
    return (r - 1) / (s.notna().sum() - 1) * 100


def save(df, name, index=False):
    df.to_csv(OUT / name, index=index, encoding="utf-8-sig")
    return OUT / name
