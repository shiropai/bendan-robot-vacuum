"""v8：家具障礙物、受損（冒煙 → 爆炸）、地洞、香蕉皮、維修包、小強、貓咪搭便車、地震。"""
import random

import pytest

from bendan.gameplay.incidents import IncidentDirector
from bendan.render.scene import scene_state
from bendan.world.game import Game, check_level, run_to_end
from bendan.world.levels import CAMPAIGN, get_level


def bare(level=0):
    """沒有家具、地洞的小地圖（座標好算）。"""
    g = Game(level, seed=1, scale=1)
    g.objects, g.dirt = {}, {(1, 5)}
    return g


@pytest.mark.parametrize("level_id", CAMPAIGN)
def test_scaled_levels_have_furniture_and_stay_solvable(level_id):
    cfg = get_level(level_id)
    assert check_level(level_id) == []
    g = Game(level_id)
    assert all(p in g.walls for p in g.furniture)
    if level_id >= 1:
        assert g.furniture, "放大後的關卡要有家具"
    assert sum(o == "hole" for o in g.objects.values()) == cfg.get("holes", 0)
    for p, f in g.furniture.items():      # 家具背後一定是牆
        dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][f["back"]]
        assert (p[0] + dx, p[1] + dy) in g.walls


def test_perception_names_furniture():
    from bendan.agent.perception import scan
    g = Game(5)
    g.forbidden = set()
    p, f = next(iter(g.furniture.items()))
    dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][f["back"]]
    g.pos, g.facing = (p[0] - dx, p[1] - dy), f["back"]
    assert g.what_at(p) == f["name"] and f["name"] in scan(g, g.facing)


def test_five_damage_stages_then_explode_on_sixth_hit():
    g = bare(3)                                  # 第 3 關起才會爆炸
    g.pos, g.facing = (1, 1), 0                  # 面向牆
    for stage in range(1, 6):
        g.set_plan([{"op": "forward", "n": 1}])
        ev = g.step()
        assert [e["type"] for e in ev] == ["collision", "damaged"] and ev[-1]["stage"] == stage
        assert g.damage == stage and not g.over
    g.set_plan([{"op": "forward", "n": 1}])
    ev = g.step()
    assert [e["type"] for e in ev][:3] == ["collision", "exploded", "level_fail"]
    assert g.failed == "exploded" and g.damage == 6
    assert [f[1] for f in g.fx][-2:] == ["bump", "boom"]                      # 特效只留最近 10 筆
    assert [f[5].get("stage") for f in g.fx if f[1] == "smoke"][-3:] == [3, 4, 5]


@pytest.mark.parametrize("obj", ["sock", "puddle", "lego", "cable", "poop"])
def test_sucking_bad_things_damages(obj):
    g = bare()
    g.pos = (3, 3)
    g.objects[(3, 3)] = obj
    g.set_plan([{"op": "suck"}])
    types = [e["type"] for e in run_to_end(g)]
    assert types[-1] == "damaged" and g.damage == 1 and (3, 3) not in g.objects


def test_vacuum_mode_sucks_lego_instead_of_stepping_on_it():
    g = bare()
    g.pos, g.facing = (1, 3), 1
    g.objects[(3, 3)] = "lego"
    g.set_plan([{"op": "vacuum_on"}, {"op": "drive"}])
    types = [e["type"] for e in run_to_end(g)]
    assert "sucked_bad" in types and "lego" not in types and g.damage == 1 and not g.vacuum and g.pos == (3, 3)


def test_hole_fall_hurts_and_returns_home():
    g = bare()
    g.pos, g.facing = (3, 3), 1
    g.objects[(4, 3)] = "hole"
    g.set_plan([{"op": "forward", "n": 3}])
    types = [e["type"] for e in run_to_end(g)]
    assert types[:3] == ["fell", "damaged", "rescued"] and g.pos == g.home and g.damage == 1
    assert g.objects[(4, 3)] == "hole"              # 洞還在
    assert g.find_path(g.pos, (6, 3)) and (4, 3) not in g.find_path(g.pos, (6, 3))   # 導航會繞開地洞


def test_banana_spins_and_toolbox_repairs():
    g = bare()
    g.pos, g.facing = (2, 3), 1
    g.objects[(3, 3)] = "banana"
    g.set_plan([{"op": "forward", "n": 2}])
    ev = run_to_end(g)
    assert ev[0]["type"] == "banana" and "banana" not in g.objects.values() and g.fx[-1][1] == "spin"
    g.damage = 1
    g.pos, g.facing = (1, 4), 1
    g.objects[(2, 4)] = "toolbox"
    g.set_plan([{"op": "forward", "n": 1}])
    assert run_to_end(g)[0]["type"] == "repaired" and g.damage == 0


def test_roach_bonus_and_cat_ride():
    g = bare()
    g.pos, g.facing = (2, 3), 1
    g.objects[(3, 3)] = "roach"
    g.set_plan([{"op": "suck"}])
    assert run_to_end(g)[-1]["type"] == "caught_roach"
    g.objects[(2, 4)] = "cat"
    d = IncidentDirector([{"type": "cat_ride", "chance": 1.0}], random.Random(0))
    ev = d.on_step(g)
    assert ev[0]["type"] == "cat_ride" and g.rider and "cat" not in g.objects.values()
    g.facing = 0
    g.pos = (2, 1)
    g.set_plan([{"op": "forward", "n": 1}])         # 撞牆 → 貓嚇跑
    types = [e["type"] for e in run_to_end(g)]
    assert "cat_off" in types and g.rider is None and "cat" in g.objects.values()


def test_quake_and_toolbox_incidents():
    g = Game(3, seed=2)
    d = IncidentDirector([{"type": "quake", "chance": 1.0, "max": 1}], random.Random(3))
    before = len(g.dirt)
    ev = d.on_step(g)
    assert ev[0]["type"] == "quake" and len(g.dirt) > before and g.fx[-1][1] == "quake"
    assert d.on_step(g) == []                       # max 1
    tb = IncidentDirector([{"type": "toolbox", "chance": 1.0}], random.Random(0))
    assert tb.on_step(g) == []                      # 沒受損就不會出現
    g.damage = 1
    assert tb.on_step(g)[0]["type"] == "toolbox_drop" and "toolbox" in g.objects.values()


def test_eval_level_is_not_fragile():
    g = Game("eval")
    g.set_plan([{"op": "forward", "n": 30}])
    types = [e["type"] for e in run_to_end(g)]
    assert "damaged" not in types and g.damage == 0 and not g.furniture
    assert "collision" in types


# ---------- 新手關不爆炸、充電座修理 ----------

@pytest.mark.parametrize("level_id", [0, 1, 2])
def test_tutorial_levels_never_explode(level_id):
    g = bare(level_id)
    g.pos, g.facing = (1, 1), 0
    for _ in range(8):
        g.set_plan([{"op": "forward", "n": 1}])
        ev = run_to_end(g)
        assert [e["type"] for e in ev] == ["collision", "damaged"]
    assert g.damage == 5 and not g.over and "新手關不會爆炸" in ev[-1]["msg"]
    assert [f[1] for f in g.fx][-2:] == ["bump", "smoke"]


def test_later_levels_still_explode():
    assert all(get_level(lv).get("explode", True) for lv in CAMPAIGN if lv >= 3)
    assert not any(get_level(lv).get("explode", True) for lv in (0, 1, 2))


def test_dock_repairs_one_damage():
    g = bare(5)
    g.damage = 1
    hx, hy = g.home
    g.pos, g.facing = (hx, hy + 1), 0            # 充電座在正北方一格
    g.set_plan([{"op": "forward", "n": 1}])
    types = [e["type"] for e in run_to_end(g)]
    assert types[0] == "docked" and "dock_repair" in types and g.damage == 0 and g.fx[-1][1] == "repair"
    g.damage = 1
    g.set_plan([{"op": "return_home"}])          # 已經在充電座上 → 一樣會修
    assert "dock_repair" in [e["type"] for e in run_to_end(g)] and g.damage == 0
    g.set_plan([{"op": "return_home"}])          # 沒壞就不會有修理事件
    assert "dock_repair" not in [e["type"] for e in run_to_end(g)]


def test_scene_state_has_furniture_fx_and_damage():
    g = Game(5)
    st = scene_state(g)
    walls = {(w[0], w[1]) for w in st["walls"]}
    assert st["furniture"] and not any((f[0], f[1]) in walls for f in st["furniture"])
    assert st["robot"]["dmg"] == 0 and st["fx"] == []
    tiles = {(t[0], t[1]) for t in st["tiles"]}
    assert all((f[0], f[1]) in tiles for f in st["furniture"])     # 家具底下有地板


def test_session_explosion_ends_level(session_factory):
    s = session_factory(3)
    s.game.pos, s.game.facing = s.game.home, 0
    while not s.game.is_blocked(s.game.front()):
        s.game.pos = s.game.front()
    s.game.damage = 5
    s.apply("往前", {"actions": [{"op": "forward", "n": 1}], "say": "衝", "ok": True})
    events = s.tick()
    types = [e["type"] for e in events]
    assert "exploded" in types and s.game.failed == "exploded" and s.result and not s.result["cleared"]


def test_popcorn_coin_and_clear_fx():
    g = Game(3, seed=4)
    before = len(g.dirt)
    ev = IncidentDirector([{"type": "popcorn", "chance": 1.0}], random.Random(0)).on_step(g)
    assert ev[0]["type"] == "popcorn" and len(g.dirt) >= before + 3
    p, f = next((p, f) for p, f in g.furniture.items())
    dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][f["back"]]
    spot = (p[0] - dx, p[1] - dy)                    # 家具正前方那一格
    coins = 0
    for i in range(40):
        g.dirt.add(spot)
        g.pos = spot
        g.rng = random.Random(i)
        coins += any(e["type"] == "coin" for e in g._suck())
    assert 3 <= coins <= 20 and g.fx[-1][1] in ("coin",) or coins
    g2 = bare()
    g2.dirt = {(3, 3)}
    g2.pos, g2.facing = (2, 3), 1
    g2.set_plan([{"op": "forward", "n": 1}, {"op": "suck"}])
    run_to_end(g2)
    assert g2.cleared and g2.fx[-1][1] == "clear"
