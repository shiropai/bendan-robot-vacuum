"""全域設定：路徑與可調參數。

log、存檔都放在專案根目錄（`bendan/` 的上一層），不管 Notebook 從哪個資料夾執行都一樣。
想改位置可以設定環境變數 `BENDAN_LOG_DIR`、`BENDAN_SAVE_DIR`。
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = Path(os.getenv("BENDAN_LOG_DIR", PROJECT_ROOT / "logs"))
SAVE_DIR = Path(os.getenv("BENDAN_SAVE_DIR", PROJECT_ROOT / "saves"))

DEFAULT_MODEL = "qwen2.5:7b"   # 提案預設；也可以試 qwen2.5:3b、llama3.1:8b


def ensure_dirs():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
