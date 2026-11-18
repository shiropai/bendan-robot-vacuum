import pytest

from bendan.world import CAMPAIGN, LEVELS, Game, check_level, run_to_end
from bendan.world.mapgen import daily_level, random_level


@pytest.mark.parametrize("level_id", list(LEVELS) + ["daily"])
def test_levels_are_solvable(level_id):
    assert check_level(level_id) == []


@pytest.mark.parametrize("seed", range(40))
def test_random_maps_are_solvable(seed):
    cfg = random_level(f"t{seed}")
    assert len({len(r) for r in cfg["map"]}) == 1
    assert check_level(f"random:t{seed}") == []


def test_daily_is_deterministic():
    assert daily_level()["map"] == daily_level()["map"]


def test_campaign_order():
    assert CAMPAIGN == sorted(CAMPAIGN) and CAMPAIGN[0] == 0


def test_basic_moves_and_suck():
    g = Game(1)
    g.set_plan([{"op": "forward", "n": 1}, {"op": "turn_left"}, {"op": "forward", "n": 2}, {"op": "suck"}])
    events = run_to_end(g)
    assert [e["type"] for e in events] == ["cleaned"]
    assert g.pos == (3, 2) and g.n_cleaned == 1


def test_collision_interrupts_plan():
    g = Game(1)
    g.set_plan([{"op": "turn_left"}, {"op": "forward", "n": 9}, {"op": "suck"}])
    events = run_to_end(g)
    assert events[-1]["type"] == "collision"
    assert not g.queue


def test_lego_is_consumed_and_interrupts():
    g = Game(1)            # 樂高在 (6, 6)
    g.pos, g.facing = (6, 5), 2
    g.set_plan([{"op": "forward", "n": 2}])
    events = run_to_end(g)
    assert "lego" in [e["type"] for e in events]
    assert (6, 6) not in g.objects and g.pos == (6, 6)


def test_poop_smears_dirt():
    g = Game(4)            # 起點 (2,4) 面東，便便在 (4,4)
    before = g.total_dirt
    g.set_plan([{"op": "forward", "n": 5}])
    events = run_to_end(g)
    assert "smeared" in [e["type"] for e in events]
    assert g.pos == (4, 4) and g.total_dirt > before and (4, 4) in g.dirt


def test_puddle_makes_robot_slip():
    g = Game(5)            # 水漬在 (3, 2)
    g.pos, g.facing = (2, 2), 1
    g.set_plan([{"op": "forward", "n": 1}])
    events = run_to_end(g)
    assert "slip" in [e["type"] for e in events]
    assert g.pos == (4, 2)


def test_suck_water_costs_battery():
    g = Game(5)
    g.pos, g.facing = (3, 2), 0     # 站在水漬上（面北，前方是牆）
    g.set_plan([{"op": "suck"}])
    events = run_to_end(g)
    assert events[0]["type"] == "suck_water"
    assert g.battery < g.battery_max - 10


def test_battery_runs_out_and_fails():
    g = Game(0)
    g.battery = 1.5
    g.set_plan([{"op": "forward", "n": 1}, {"op": "suck"}])
    events = run_to_end(g)
    types = [e["type"] for e in events]
    assert "out_of_battery" in types and "level_fail" in types
    assert g.failed == "out_of_battery" and g.over


def test_low_battery_warning_once():
    g = Game(0)
    g.battery = g.battery_max * 0.26
    g.set_plan([{"op": "turn_left"}] * 8)
    types = [e["type"] for e in run_to_end(g)]
    assert types.count("low_battery") == 1


def test_return_home_charges():
    g = Game(1)
    g.battery = 50
    g.set_plan([{"op": "return_home"}])
    types = [e["type"] for e in run_to_end(g)]
    assert g.pos == g.home and "charged" in types and g.battery == g.battery_max


def test_return_home_avoids_forbidden_room():
    g = Game(2)
    g.pos, g.facing = (7, 3), 1
    g.set_plan([{"op": "return_home"}])
    run_to_end(g)
    assert g.pos == g.home and g.violations == 0


def test_level_clear_requires_home_when_needed():
    g = Game(0)
    g.need_home = True
    g.dirt.clear()
    g.set_plan([{"op": "turn_left"}])
    run_to_end(g)
    assert not g.cleared
    g.set_plan([{"op": "return_home"}])
    types = [e["type"] for e in run_to_end(g)]
    assert g.cleared and "level_clear" in types


def test_over_game_ignores_steps():
    g = Game(0)
    g.fail("time_up", "x")
    g.set_plan([{"op": "forward", "n": 1}])
    assert g.step() == [] and g.pos == g.start[0]


def test_low_battery_warns_when_only_enough_to_get_home():
    """電池小的關卡：還沒到 25%，但電量只夠走回充電座時就要先警告。"""
    g = Game(5)                          # 電池 60，充電座在 (1,1)
    g.pos, g.facing = (12, 7), 3         # 右下角，離充電座很遠
    d = g.home_distance()
    g.battery = d + 6.1                  # 約 38%，高於 25%（轉一次 −0.2 後就只夠回家）
    g.set_plan([{"op": "turn_left"}])
    types = [e["type"] for e in run_to_end(g)]
    assert "low_battery" in types and g.low_battery and g.battery_pct > 25
