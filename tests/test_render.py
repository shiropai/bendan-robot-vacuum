"""SVG 畫面、方向輔助、HUD、遊戲視窗（不需要瀏覽器的部分）。"""
import time

import pytest
from conftest import drive

from bendan.render import direction_aids, facing_text, history_html, hud_html, render_svg, side_html
from bendan.world import CAMPAIGN, Game


@pytest.mark.parametrize("level_id", CAMPAIGN + ["daily"])
@pytest.mark.parametrize("view", ["iso", "top"])
def test_svg_renders_every_level(level_id, view):
    svg = render_svg(Game(level_id), view=view, thinking=True, mood="不爽", emotion="生氣")
    assert svg.startswith("<svg") and svg.endswith("</svg>") and "viewBox" in svg


def test_direction_aids_mark_front_left_right():
    g = Game(0)                      # 起點 (2,3) 面東，前方 5 格空地
    aids = direction_aids(g)
    assert [aids[(2 + k, 3)] for k in range(1, 6)] == ["1", "2", "3", "4", "5"]
    assert aids[(2, 2)] == "左" and aids[(2, 4)] == "右" and aids[(1, 3)] == "後"
    assert facing_text(g).startswith("面向東") and "前方可走 5 格" in facing_text(g)


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
        assert "請往前走三格然後吸" in ui.history.value and "<svg" in ui.board.value
        ui._on_view(None)
        ui._render(force=True)
        assert ui.session.view == "top"
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
    assert any(t[3] == 0 for t in st["tiles"]) and ["1"] == [a[2] for a in st["aids"] if a[2] == "1"]
    html = scene_html(Game(0))
    data = html.split("class='bd-state'>")[1].split("</script>")[0]
    assert json.loads(data)["w"] == Game(0).w


def test_view_cycles_through_3d(session_factory):
    from bendan.ui.commands import handle_slash
    s = session_factory(0)
    assert [handle_slash(s, "/view") and s.view for _ in range(3)] == ["top", "3d", "iso"]
    handle_slash(s, "/view 3d")
    assert s.view == "3d"


def test_3d_asset_bundle_has_furniture_and_pets():
    import json

    from bendan.render.assets3d import asset_bundle_json, assets_html
    d = json.loads(asset_bundle_json().replace("<\\/", "</"))
    assert {"loungeSofa", "kitchenFridge", "toilet", "rugRectangle"} <= set(d["furniture"])
    assert all(v["obj"].lstrip().startswith(("#", "mtllib", "o ", "v ")) for v in d["furniture"].values())
    assert set(d["pets"]) == {"cat", "dog"} and "bd-assets" in assets_html()


def test_scene3d_js_is_embedded_in_game_window():
    from bendan.ui.widget_mode import SCENE3D_JS, _js_loader
    assert "ROOM_FURNITURE" in SCENE3D_JS and "/*SCENE3D*/" not in _js_loader()
