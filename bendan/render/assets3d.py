"""3D 素材包：家具（Kenney，CC0）＋會動的寵物（Quaternius，CC0），見 `bendan/assets/3d/LICENSE.md`。

第一次切到 3D 視角時，整包（約 2 MB）透過一個隱藏的 widget 送到瀏覽器一次，之後就不用再傳。
用這種方式而不是讓瀏覽器自己去抓檔案，是因為課程 JupyterHub 和自己電腦的檔案網址不一樣，送資料最穩。
"""
import base64
import json
from functools import lru_cache
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "3d"


@lru_cache(maxsize=1)
def asset_bundle_json():
    furniture = {}
    for obj in sorted((ASSET_DIR / "furniture").glob("*.obj")):
        mtl = obj.with_suffix(".mtl")
        furniture[obj.stem] = {"obj": obj.read_text(encoding="utf-8"),
                               "mtl": mtl.read_text(encoding="utf-8") if mtl.exists() else ""}
    pets = {p.stem: base64.b64encode(p.read_bytes()).decode() for p in sorted((ASSET_DIR / "pets").glob("*.glb"))}
    return json.dumps({"furniture": furniture, "pets": pets}, ensure_ascii=False).replace("</", "<\\/")


def assets_html():
    return f"<script type='application/json' class='bd-assets'>{asset_bundle_json()}</script>"
