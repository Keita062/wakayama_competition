"""13_総合計画 ダウンロード

- データ名: 和歌山県内6市の総合計画（現行計画＋策定中の次期計画の素案・骨子）
- 作成機関: 各市（和歌山市・田辺市・橋本市・岩出市・海南市・紀の川市）
- 用途    : 各市の計画が挙げる「現状と課題」「重点施策」「成果指標（KPI）」の確認（02_memo/総合計画_要点.md）
- 公式ページ:
    和歌山市: https://www.city.wakayama.wakayama.jp/shisei/1009206/1009403/1002808.html
        第5次和歌山市長期総合計画（H29〜R8年度）。次期（第6次）の素案等は公式サイト上で確認できず（2026-10-06時点）
    田辺市  : https://www.city.tanabe.lg.jp/machizukuri/gyoseiunei/7/kikakukeikaku/15/1/4110.html （第2次 基本構想・前期）
              https://www.city.tanabe.lg.jp/machizukuri/gyoseiunei/7/kikakukeikaku/15/1/4112.html （第2次 後期基本計画 R4〜R8年度）
              https://www.city.tanabe.lg.jp/machizukuri/gyoseiunei/7/kikakukeikaku/15/2/4113.html （第3次 基本構想（案） R9〜R18年度）
    橋本市  : https://www.city.hashimoto.lg.jp/guide/sogoseisakubu/seisaku_kikaku/tyoukikeikaku/tyoukiplan/1524127614792.html （第2次 H30〜R9年度）
              https://www.city.hashimoto.lg.jp/guide/sogoseisakubu/seisaku_kikaku/tyoukikeikaku/dai2jichoukeikouki/tyoukisouogukeikakukoukisakutei.html （後期）
              ※第3次（R10年度〜）は審議会が始まった段階で素案なし → 審議会ページの本文を .md で保存
    岩出市  : https://www.city.iwade.lg.jp/soshiki/2/10749.html （第3次 後期基本計画 R8〜R12年度、R8.3策定）
    海南市  : https://www.city.kainan.lg.jp/kakubusho/soumubu/kikakuzaiseika/kikakuzaiseikatorikumi/sogo_keikaku/dai4ji/dai4jisakutei/7351.html
              第4次海南市総合計画（R7.9策定。基本構想R7〜概ね10年／基本計画R7〜R11年度）
    紀の川市: https://www.city.kinokawa.lg.jp/004/dai2jityoukei_midashi_1.html （第2次 基本構想・前期）
              https://www.city.kinokawa.lg.jp/004/dai2ji_tyoukisougoukeikaku_kouki.html （第2次 後期 R5〜R8年度）
              https://www.city.kinokawa.lg.jp/004/2026-0423-1035-54.html （第3次 審議会資料：基本構想案・序論素案・基本計画素案）
- 分冊があるものは「全体版（一括）」を優先し、全体版が無い／大きすぎる場合は基本構想・基本計画の部分を取得
  （100MB超のファイルは無し）
- PDFは公表されたまま保存し、ファイル名だけ分かりやすい日本語名にする（末尾に元ファイル名を残す）
- 取得日  : 2026-10-06
"""
import html
import re
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parents[2] / "04_data" / "01_raw" / "13_総合計画"
HEADERS = {"User-Agent": "Mozilla/5.0"}
ACCESS_DATE = "2026-10-06"

# (市名, 保存名（拡張子・元ファイル名なし）, URL)
TARGETS = [
    # --- 和歌山市：第5次長期総合計画（H29〜R8年度） ---
    ("和歌山市", "第5次和歌山市長期総合計画_全体版",
     "https://www.city.wakayama.wakayama.jp/_res/projects/default_project/_page_/001/002/808/5jichoukisougoukeikaku.pdf"),
    ("和歌山市", "第5次和歌山市長期総合計画_実施計画_R6-R8",
     "https://www.city.wakayama.wakayama.jp/_res/projects/default_project/_page_/001/002/808/jisshikeikaku_R6-8.pdf"),
    # --- 田辺市：第2次総合計画（H29〜R8年度）＋第3次（R9〜）基本構想案 ---
    ("田辺市", "第2次田辺市総合計画_全体版_基本構想・前期基本計画",
     "https://www.city.tanabe.lg.jp/material/files/group/2/dai2ji_sogokeikaku.pdf"),
    ("田辺市", "第2次田辺市総合計画_後期基本計画_全体版_R4-R8",
     "https://www.city.tanabe.lg.jp/material/files/group/2/dai2ji_kouki.pdf"),
    ("田辺市", "第2次田辺市総合計画_第10期実施計画_R8-R10",
     "https://www.city.tanabe.lg.jp/material/files/group/2/dai10ki_jissi.pdf"),
    ("田辺市", "第3次田辺市総合計画_基本構想（案）_パブコメ版_R8.7",
     "https://www.city.tanabe.lg.jp/material/files/group/2/public-comment.pdf"),
    ("田辺市", "第3次田辺市総合計画_審議会第2回会議録_R8.3.30",
     "https://www.city.tanabe.lg.jp/material/files/group/2/kaigiroku2_260330.pdf"),
    # --- 橋本市：第2次長期総合計画（H30〜R9年度） ---
    ("橋本市", "第2次橋本市長期総合計画_第1章_総合計画の策定にあたって",
     "https://www.city.hashimoto.lg.jp/material/files/group/67/2chapter1.pdf"),
    ("橋本市", "第2次橋本市長期総合計画_第2章_基本構想",
     "https://www.city.hashimoto.lg.jp/material/files/group/67/2chapter2.pdf"),
    ("橋本市", "第2次橋本市長期総合計画_後期基本計画_全体版",
     "https://www.city.hashimoto.lg.jp/material/files/group/67/2thtyoukeikoukihonepen.pdf"),
    # --- 岩出市：第3次長期総合計画（R3〜R12年度）後期基本計画（R8〜R12年度） ---
    ("岩出市", "第3次岩出市長期総合計画_後期基本計画_全編_R8.3",
     "https://www.city.iwade.lg.jp/uploaded/attachment/9010.pdf"),
    # --- 海南市：第4次総合計画（R7.9策定） ---
    ("海南市", "第4次海南市総合計画_全体版",
     "https://www.city.kainan.lg.jp/material/files/group/5/sougoukeikaku4.pdf"),
    ("海南市", "第4次海南市総合計画_概要版",
     "https://www.city.kainan.lg.jp/material/files/group/5/sougoukeikakugaiyoubann.pdf"),
    # --- 紀の川市：第2次長期総合計画（H30〜R8年度）＋第3次（R9〜）素案 ---
    ("紀の川市", "第2次紀の川市長期総合計画_基本構想",
     "https://www.city.kinokawa.lg.jp/004/files/02_choukei_kihonkousou.pdf"),
    ("紀の川市", "第2次紀の川市長期総合計画_後期基本計画_全体版_R5-R8",
     "https://www.city.kinokawa.lg.jp/004/files/dai2ji_kouki_all.pdf"),
    ("紀の川市", "第3次紀の川市長期総合計画_策定方針_R7.8",
     "https://www.city.kinokawa.lg.jp/004/files/sakuteihoushin.pdf"),
    ("紀の川市", "第3次紀の川市長期総合計画_基本構想（案）_パブコメ反映後",
     "https://www.city.kinokawa.lg.jp/004/files/5-3.pdf"),
    ("紀の川市", "第3次紀の川市長期総合計画_骨子（案）",
     "https://www.city.kinokawa.lg.jp/004/files/5-5.pdf"),
    ("紀の川市", "第3次紀の川市長期総合計画_序論素案_第7回審議会",
     "https://www.city.kinokawa.lg.jp/004/files/jyorons2.pdf"),
    ("紀の川市", "第3次紀の川市長期総合計画_施策体系_第7回審議会",
     "https://www.city.kinokawa.lg.jp/004/files/taikeiso.pdf"),
    ("紀の川市", "第3次紀の川市長期総合計画_基本計画（素案）_第7回審議会",
     "https://www.city.kinokawa.lg.jp/004/files/keikakusoan.pdf"),
]

# PDFが無い（次期計画の策定状況のみ）ページ → 本文テキストを .md で保存
# (市名, 保存名, URL, 本文の開始目印, 本文の終了目印)
PAGES_AS_MD = [
    ("橋本市", "第3次橋本市長期総合計画_策定状況_審議会ページ",
     "https://www.city.hashimoto.lg.jp/guide/sogoseisakubu/seisaku_kikaku/tyoukikeikaku/third_tyokisogokeikaku_zenki/23496.html",
     "更新日", "橋本市 総合政策部"),
    ("橋本市", "第3次橋本市長期総合計画_策定状況_プロポーザルページ",
     "https://www.city.hashimoto.lg.jp/guide/sogoseisakubu/seisaku_kikaku/tyoukikeikaku/third_tyokisogokeikaku_zenki/22305.html",
     "更新日", "様式第１号"),
]


def html_to_text(raw: str) -> str:
    """HTMLから本文テキストを素朴に取り出す（タグ除去・空行の圧縮）."""
    t = re.sub(r"(?s)<(script|style).*?</\1>", "", raw)
    t = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>|</div>|</tr>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return "\n".join(line.strip() for line in t.splitlines() if line.strip())


def main() -> None:
    session = requests.Session()
    session.headers.update(HEADERS)

    for city, name, url in TARGETS:
        out_dir = OUT_DIR / city
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{name}_{Path(url).name}"
        resp = session.get(url, timeout=300)
        resp.raise_for_status()
        out.write_bytes(resp.content)
        print(f"saved {city}/{out.name} ({len(resp.content):,} bytes) <- {url}")

    for city, name, url, start, end in PAGES_AS_MD:
        out_dir = OUT_DIR / city
        out_dir.mkdir(parents=True, exist_ok=True)
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        text = html_to_text(resp.text)
        i = text.find(start)
        j = text.find(end, i + 1)
        body = text[i: j if j > 0 else None] if i >= 0 else text
        out = out_dir / f"{name}.md"
        out.write_text(f"# {name}\n\n- 出典: {url}\n- 取得日: {ACCESS_DATE}\n"
                       f"- 備考: PDFの計画書・素案は未公表のため、ページ本文を保存\n\n---\n\n{body}\n",
                       encoding="utf-8")
        print(f"saved {city}/{out.name} <- {url}")


if __name__ == "__main__":
    main()
