"""v6：放大的地圖、加倍的灰塵、「一直往前開、喊停才停」的連續移動、吸塵模式。"""
import pytest
from conftest import drive

from bendan.world import CAMPAIGN, Game, check_level, get_level, run_to_end


@pytest.mark.parametrize("level_id", CAMPAIGN + ["daily"])
def test_scaled_levels_are_bigger_and_solvable(level_id):
    small, big = Game(level_id, scale=1), Game(level_id)
    assert len(big.floor_tiles()) >= 3 * len(small.floor_tiles())
    assert len(big.dirt) >= 2 * len(small.dirt) - 1
    assert check_level(level_id) == []


def test_eval_scene_is_never_scaled():
    assert get_level("eval") is get_level("eval", scale=1)


def test_drive_keeps_going_until_wall():
    g = Game(0)
    x0, _ = g.pos
    g.set_plan([{"op": "drive"}])
    for _ in range(3):
        g.step()
    assert g.driving and g.pos[0] == x0 + 3            # 還在開，沒有自己停
    events = run_to_end(g)
    assert not g.driving and events[-1]["type"] == "collision" and g.pos[0] == g.w - 2


def test_vacuum_mode_cleans_on_the_way_and_jams_on_sock():
    g = Game(0)
    g.pos, g.facing = (1, 1), 1
    g.dirt = {(3, 1), (3, 5)}
    g.objects = {(5, 1): "sock"}
    g.set_plan([{"op": "vacuum_on"}, {"op": "drive"}])
    events = run_to_end(g)
    types = [e["type"] for e in events]
    assert types[:1] == ["vacuum"] and "cleaned" in types and types[-1] == "jammed"
    assert g.pos == (5, 1) and not g.vacuum and not g.queue


def test_stop_and_steering_while_driving(session_factory):
    s = session_factory(0)
    s.apply("往前", {"actions": [{"op": "drive"}], "say": "衝", "ok": True})
    s.tick()
    assert s.game.driving
    s.apply("右轉", {"actions": [{"op": "turn_right"}], "say": "好", "ok": True})
    facing = s.game.facing
    s.tick()
    assert s.game.facing == (facing + 1) % 4 and s.game.driving      # 轉完繼續開
    assert "🚗 繼續開" in s.history[-1]["flags"]
    drive(s, "停")
    assert not s.game.driving and not s.busy()


def test_fake_llm_turns_plain_forward_into_drive(session_factory):
    s = session_factory(0)
    res = s.think("往前")
    assert res["actions"] == [{"op": "drive"}]
    assert s.think("往前走三格")["actions"] == [{"op": "forward", "n": 3}]
    assert s.think("開吸塵然後往前")["actions"] == [{"op": "vacuum_on"}, {"op": "drive"}]


def test_plain_forward_becomes_drive_but_counts_stay():
    from bendan.session import drive_fix
    f1 = [{"op": "forward", "n": 1}]
    assert drive_fix("往前", f1) == [{"op": "drive"}]
    assert drive_fix("右轉然後往前", [{"op": "turn_right"}] + f1 + [{"op": "suck"}]) == [{"op": "turn_right"}, {"op": "drive"}]
    assert drive_fix("往前走三格", [{"op": "forward", "n": 3}]) == [{"op": "forward", "n": 3}]
    assert drive_fix("往前一點", f1) == f1
