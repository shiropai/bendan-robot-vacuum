#!/usr/bin/env bash
# 在課程 JupyterHub（期末專題的小組帳號）建立笨笨掃地機的 Conda 環境，並註冊成 Jupyter Kernel。
#
#   cd ~/笨笨掃地機 && bash scripts/setup_jupyterhub_env.sh          # 預設環境名稱 bendan
#
# 做的事：
#   1. 用 conda 建一個 Python 3.11 的環境（已經有就沿用）
#   2. pip 安裝 requirements.txt（openai、ipywidgets、pandas、matplotlib、pytest、nbclient）＋ ipykernel
#   3. 註冊 Kernel「Python (笨笨掃地機)」：notebook 右上角選它就能用
#   4. 跑一次測試（離線 FakeLLM，不會用到 GPU 或 API）
# API 設定（OPENAI_BASE_URL／OPENAI_API_KEY）沿用 JupyterHub 已經設好的環境變數，腳本不會碰到 API Key。
set -euo pipefail
ENV_NAME="${1:-bendan}"
cd "$(dirname "$0")/.."

if ! command -v conda >/dev/null 2>&1; then
  for c in /opt/conda/bin/conda /opt/miniconda3/bin/conda "$HOME/miniconda3/bin/conda" "$HOME/anaconda3/bin/conda"; do
    if [ -x "$c" ]; then PATH="$(dirname "$c"):$PATH"; break; fi
  done
fi
command -v conda >/dev/null 2>&1 || { echo "❌ 找不到 conda：請先照助教課的示範安裝 Miniconda"; exit 1; }
eval "$(conda shell.bash hook)"

if conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "✔ Conda 環境 $ENV_NAME 已經存在，沿用"
else
  conda create -y -n "$ENV_NAME" python=3.11
fi
conda activate "$ENV_NAME"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt ipykernel
python -m ipykernel install --user --name "$ENV_NAME" --display-name "Python (笨笨掃地機)"
python -m pytest -q
echo "✅ 完成：notebook 右上角的 Kernel 選「Python (笨笨掃地機)」"
