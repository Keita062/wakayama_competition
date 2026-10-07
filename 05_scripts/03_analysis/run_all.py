"""分析を前処理からレポート作成まで順に実行する。

前提：04_data/02_processed/01_市区町村別_個別KPI.csv が作成済み（05_scripts/02_build/01_市区町村別KPI表の作成.py）
実行：set_up/.venv の Python で `python run_all.py`（このフォルダで）
"""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
STEPS = sorted(p.name for p in HERE.glob("[0-9][0-9]_*.py"))

for name in STEPS:
    print(f"===== {name}")
    runpy.run_path(str(HERE / name), run_name="__main__")
