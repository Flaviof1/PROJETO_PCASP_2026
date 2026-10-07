from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "pcasp.sqlite3"
INITIAL_WORKBOOK = DATA_DIR / "PCASP_TCEMG-2026_v12.2.xlsx"
WEB_DIR = Path(__file__).resolve().parent / "web"
HOST = "127.0.0.1"
PORT = 8765
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
