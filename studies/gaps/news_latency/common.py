from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "gaps_news"
DATA.mkdir(parents=True, exist_ok=True)
OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
