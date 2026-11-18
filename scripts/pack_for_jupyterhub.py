#!/usr/bin/env python3
"""把專案打包成 zip，方便上傳到課程 JupyterHub（JupyterLab 不能直接上傳資料夾）。

    python scripts/pack_for_jupyterhub.py         # → dist/bendan_jupyterhub.zip

上傳到 JupyterHub 後，在 Terminal 執行：
    python3 -c "import zipfile; zipfile.ZipFile('bendan_jupyterhub.zip').extractall('笨笨掃地機')"
再打開 笨笨掃地機/notebooks/01_快速開始_遊玩.ipynb，Kernel 選「Python 3 (ipykernel)」。
（實測課程伺服器的 Terminal 沒有 jupyter 指令，但有 python3；unzip 指令不一定有，所以用 Python 解壓。）
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ["bendan", "notebooks", "tests", "scripts", "docs/architecture.md", "docs/gameplay.md",
           "docs/evaluation_results.md", "docs/voice_input.md", "docs/difficulty.md", "README.md", "requirements.txt"]
SKIP_PARTS = {"__pycache__", ".ipynb_checkpoints", "archive"}


def main():
    out = ROOT / "dist" / "bendan_jupyterhub.zip"
    out.parent.mkdir(exist_ok=True)
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in INCLUDE:
            p = ROOT / item
            if not p.exists():
                continue
            files = [p] if p.is_file() else sorted(f for f in p.rglob("*") if f.is_file())
            for f in files:
                if SKIP_PARTS & set(f.relative_to(ROOT).parts):
                    continue
                z.write(f, f.relative_to(ROOT))
                n += 1
    print(f"✅ {out}（{n} 個檔案，{out.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
