"""俯視 SVG（文字模式用）、HUD、3D 遊戲視窗（不需要瀏覽器的部分）。"""
import json
import time

import pytest
from conftest import drive

from bendan.render import facing_text, history_html, hud_html, render_svg, side_html
from bendan.world import CAMPAIGN, Game


@pytest.mark.parametrize("level_id", CAMPAIGN + ["daily"])
def test_svg_renders_every_level(level_id):
    svg = render_svg(Game(level_id), thinking=True, mood="不爽", emotion="生氣")
    assert svg.startswith("<svg") and svg.endswith("</svg>") and "viewBox" in svg
    assert "data-proj='top'" in svg and "iso" not in svg          # v8：2.5D 等角視角已移除


@pytest.mark.usefixtures("small_maps")
def test_no_floor_numbers_or_side_labels_and_facing_text():
    """v7：地板不再標 1 2 3…、也沒有「左／右／後」字樣（看笨笨的箭頭就知道朝向）。"""
    g = Game(0)                      # 起點 (2,3) 面東，前方 5 格空地
    svg = render_svg(g)
    assert ">左<" not in svg and ">右<" not in svg and ">後<" not in svg and ">1<" not in svg
    assert facing_text(g).startswith("面向東") and "前方是牆壁" in facing_text(g) and "格" not in facing_text(g)


def test_top_view_draws_furniture():
    g = Game(3)
    assert g.furniture and "🛋️" in render_svg(g) or "📚" in render_svg(g)


def test_end_banner_and_fog():
    g = Game(0)
    g.cleared = True
    assert "CLEAR" in render_svg(g)
    assert "#23263a" in render_svg(Game(9))        # 停電關有黑色迷霧


def test_hud_puts_history_under_bubble(session_factory):
    s = session_factory(1, "serious")
    drive(s, "請往前走兩格")
    page = hud_html(s, "好", [])
    assert page.index("笨笨：") < page.index("指令紀錄") < page.index("面向")
    assert "請往前走兩格" in history_html(s) and "data-cmd" in history_html(s)
    assert "面向" in side_html(s)


def test_widget_game_window_smoke(progress):
    pytest.importorskip("ipywidgets")
    from bendan.ui.widget_mode import WidgetGame
    ui = WidgetGame(0, "serious", tick=0.01, progress=progress, seed=0)
    try:
        assert "bendan-game" in ui.box._dom_classes and "new Function" in ui.js.value
        ui._take_input("請往前走三格然後吸")
        for _ in range(300):
            if ui.future is None and not ui.session.busy() and ui.session.history and ui.session.history[-1]["done"]:
                break
            time.sleep(0.01)
        assert ui.session.history[-1]["cmd"] == "請往前走三格然後吸"
        ui._render(force=True)
        assert "請往前走三格然後吸" in ui.history.value and "<svg" not in ui.board.value     # v8：只有 3D
        st = json.loads(ui.board.value.split("class='bd-state'>")[1].split("</script>")[0])
        assert (st["robot"]["x"], st["robot"]["y"]) == ui.session.game.pos and "furniture" in st
        assert "bd-assets" in ui.assets3d.value and not hasattr(ui, "btn_view")
        bot = json.loads(ui.botw.value.split("'bd-botjs'>")[1].split("</script>")[0])
        assert (bot["x"], bot["y"]) == ui.session.game.pos and bot["tts"] and bot["sayN"] >= 2
    finally:
        ui.quit()
    assert ui.cmd.disabled and "window.close" in ui.head.value


def test_scene_state_for_3d():
    import json

    from bendan.render.scene import scene_html, scene_state
    g = Game(9)                                   # 停電關：看不到的東西不能送出去
    st = scene_state(g, mood="開心", emotion="得意")
    assert st["robot"]["x"] == g.pos[0] and st["robot"]["facing"] == g.facing and st["robot"]["emotion"] == "😎"
    assert all(g.visible((x, y)) for x, y in st["dirt"]) and len(st["dirt"]) < len(g.dirt)
    assert any(t[3] == 0 for t in st["tiles"]) and "aids" not in st
    html = scene_html(Game(0))
    data = html.split("class='bd-state'>")[1].split("</script>")[0]
    assert json.loads(data)["w"] == Game(0).w


def test_view_command_explains_3d_only(session_factory):
    from bendan.ui.commands import handle_slash
    s = session_factory(0)
    assert "3D" in handle_slash(s, "/view")["say"] and s.view == "3d"


def test_3d_asset_bundle_has_furniture_and_pets():
    import json

    from bendan.render.assets3d import asset_bundle_json, assets_html
    d = json.loads(asset_bundle_json().replace("<\\/", "</"))
    assert {"loungeSofa", "kitchenFridge", "toilet", "rugRectangle"} <= set(d["furniture"])
    assert all(v["obj"].lstrip().startswith(("#", "mtllib", "o ", "v ")) for v in d["furniture"].values())
    assert set(d["pets"]) == {"cat", "dog"} and "bd-assets" in assets_html()


def test_scene3d_js_is_embedded_in_game_window():
    from bendan.ui.widget_mode import SCENE3D_JS, _js_loader
    assert "FURN_MODELS" in SCENE3D_JS and "WALL_H = 2.4" in SCENE3D_JS and "/*SCENE3D*/" not in _js_loader()


def test_scene3d_models_cover_every_furniture_key():
    """v8：furnish.py 會擺的每一種家具，3D 都要有對應的模型（而且模型檔真的存在）。"""
    import re

    from bendan.render.assets3d import ASSET_DIR
    from bendan.ui.widget_mode import SCENE3D_JS
    from bendan.world.furnish import NAMES
    block = SCENE3D_JS.split("var FURN_MODELS = {")[1].split("};")[0]
    keys = set(re.findall(r"(\w+): \[\[", block))
    assert set(NAMES) <= keys
    for name in set(re.findall(r"'(\w+)'", block)):
        assert (ASSET_DIR / "furniture" / f"{name}.obj").exists(), name


def test_widget_title_screen_start_and_back(progress):
    pytest.importorskip("ipywidgets")
    from bendan.ui.widget_mode import WidgetGame
    ui = WidgetGame(0, "serious", tick=0.01, progress=progress, seed=0)
    try:
        assert ui.on_title and ui.title_screen.layout.display == "flex" and ui.game_screen.layout.display == "none"
        assert "bd-cover-main" in ui.cover.value and "data:image/jpeg;base64," in ui.cover.value
        assert ui.dd_level in ui.title_screen.children and ui.btn_start in ui.title_screen.children
        assert not hasattr(ui, "btn_next")                                   # 遊戲中不能選關
        ui.dd_level.value = 2
        assert "第 2 關" in ui.level_info.value and ui.session.game.level_id == 0   # 選了還沒開始
        ui._on_start(None)
        assert not ui.on_title and ui.session.game.level_id == 2 and ui.game_screen.layout.display == "flex"
        assert "data-act='cam'" in ui._head_html()                           # 右上：換視角
        assert "data-act='quality'" in ui._head_html() and "data-act='stats'" in ui._head_html()   # 3D 畫質／效能面板
        ui._take_input("/level 5")
        assert ui.session.game.level_id == 2 and "返回" in ui.say            # 遊戲中打指令也不能換關
        ui._on_back(None)
        assert ui.on_title and ui.title_screen.layout.display == "flex"
    finally:
        ui.quit()



def test_hud_splits_mood_change_into_tone_and_events(session_factory):
    """罵它 -15，但同一句吸到灰塵又加回來：HUD 要分開寫，不然看起來像「罵了反而變開心」。"""
    from bendan.render.hud import meters_html
    s = session_factory(0, "silly")
    drive(s, "笨蛋，往前走三格然後吸")
    html_ = meters_html(s)
    assert "這句：語氣 -15" in html_
    s.mood.apply_events([{"type": "cleaned"}] * 3)     # 同一句又吸到三坨灰塵
    assert "這句：語氣 -15、事件 +9" in meters_html(s)
    drive(s, "右轉")                                 # 新的一句：重新計算
    assert "語氣 -15" not in meters_html(s)


def test_robot_stops_to_listen_while_the_model_thinks(progress):
    """新計畫是照下指令那一刻的位置算的：模型在想的時候笨笨不能照舊計畫繼續走，不然新計畫會從錯的位置開始（走到乾淨的地方空吸）。"""
    pytest.importorskip("ipywidgets")
    from concurrent.futures import Future

    from bendan.ui.widget_mode import WidgetGame
    ui = WidgetGame(1, "serious", tick=0.01, progress=progress, seed=0)
    try:
        s = ui.session
        s.apply("往前", {"actions": [{"op": "forward", "n": 6}], "say": "好", "ok": True, "format_ok": True,
                         "raws": [], "latency": 0}, kind="local")
        pending = Future()                              # 模型還在想
        ui.future_info = {"command": "去吸左邊那坨", "kind": "command", "depth": 0}
        ui.future = pending
        time.sleep(0.03)
        pose = (s.game.pos, s.game.facing, s.game.steps)
        time.sleep(0.15)                                 # 十幾個 tick
        assert (s.game.pos, s.game.facing, s.game.steps) == pose and s.busy()
        pending.set_result({"actions": [], "say": "好", "ok": True, "format_ok": True, "raws": [], "latency": 1.2})
        for _ in range(100):
            if ui.future is None:
                break
            time.sleep(0.01)
        assert ui.future is None and not ui._listening()
    finally:
        ui.quit()
