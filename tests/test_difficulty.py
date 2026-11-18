"""v3 難度系統：恍神、記性差、步數限制、停電、視野、導航壞掉、會累、護欄停用、指令紀錄。"""
import random

import pytest
from conftest import drive

from bendan.agent import Agent, describe_world
from bendan.gameplay import Mood, Progress
from bendan.gameplay.quirks import QUIRKS, apply_quirk, limit_plan, maybe_quirk, quirk_chance
from bendan.ui.commands import handle_slash
from bendan.world import CAMPAIGN, FINAL_LEVEL, LEVELS, Game, run_to_end

class AlwaysRng:
    """random() 永遠是 0 → 機率判定一定成立。"""

    def random(self):
        return 0.0

    def shuffle(self, x):
        pass

    def choice(self, x):
        return x[0]


PLAN = [{"op": "forward", "n": 2}, {"op": "turn_left"}, {"op": "forward", "n": 1}, {"op": "suck"}]


def test_campaign_has_ten_levels_plus_tutorial():
    assert CAMPAIGN == list(range(11)) and FINAL_LEVEL == 10


def test_difficulty_increases_along_campaign():
    chance = [LEVELS[k].get("quirks", {}).get("chance", 0) for k in CAMPAIGN]
    assert chance == sorted(chance) and chance[0] == 0 and chance[-1] >= 0.2
    assert all(LEVELS[k].get("route_hints", True) is False for k in range(6, 11))
    assert all(LEVELS[k].get("new") for k in range(1, 11))       # 每關都有「本關新機制」說明


@pytest.mark.parametrize("kind", sorted(QUIRKS))
def test_each_quirk_changes_plan_or_declines(kind):
    new, msg = apply_quirk(kind, PLAN, random.Random(0))
    assert new is not None and msg and new != PLAN
    assert PLAN[0] == {"op": "forward", "n": 2}                  # 原本的計畫沒被改到


def test_quirk_specifics():
    rng = random.Random(1)
    assert [a["op"] for a in apply_quirk("mirror", PLAN, rng)[0]][1] == "turn_right"
    assert apply_quirk("forget_suck", PLAN, rng)[0][-1]["op"] != "suck"
    assert len(apply_quirk("lazy", PLAN, rng)[0]) == 2
    assert apply_quirk("deaf", PLAN, rng)[0] == []
    assert apply_quirk("mirror", [{"op": "suck"}], rng) == (None, None)     # 沒有轉彎就不能左右不分


def test_quirk_chance_depends_on_mood_and_mode():
    cfg = {"quirks": {"chance": 0.2}}
    assert quirk_chance(cfg, Mood(90)) == pytest.approx(0.1)
    assert quirk_chance(cfg, Mood(60)) == pytest.approx(0.2)
    assert quirk_chance(cfg, Mood(10)) == pytest.approx(0.4)
    assert quirk_chance(cfg, Mood(60), mode="serious") == pytest.approx(0.1)
    assert quirk_chance({}, Mood(10)) == 0


def test_stop_and_home_are_never_changed():
    cfg = {"quirks": {"chance": 1.0}}
    for plan in ([{"op": "return_home"}], [{"op": "stop"}], []):
        assert maybe_quirk(plan, cfg, random.Random(0))[1] is None


def test_limit_plan():
    acts, ev = limit_plan(PLAN, 3)
    assert len(acts) == 3 and ev["type"] == "forgot" and ev["dropped"] == 1
    assert limit_plan(PLAN, None) == (PLAN, None)


def test_session_applies_forced_quirk_and_records_history(session_factory):
    s = session_factory(1, "serious")
    s.game.cfg = dict(s.game.cfg, quirks={"chance": 1.0, "pool": ["mirror"]})
    s.rng = AlwaysRng()
    events = drive(s, "左轉")
    assert any(e["type"] == "quirk" for e in events)
    assert s.game.facing == 2            # 起點面東，左轉應該面北，恍神後變成右轉 → 面南
    h = s.history[-1]
    assert h["cmd"] == "左轉" and h["done"] and any("左右不分" in f for f in h["flags"])


def test_session_max_plan_truncates(session_factory):
    s = session_factory(8, "serious")
    s.game.cfg = dict(s.game.cfg, quirks=None)
    res = {"actions": PLAN + [{"op": "turn_right"}], "say": "好", "ok": True}
    events = s.apply("一長串", res)
    assert any(e["type"] == "forgot" for e in events)
    assert len(s.game.queue) == 4          # forward 2、turn_left、forward 1 → 4 個微步驟（suck、turn_right 忘了）
    assert "🧠 忘了後面" in s.history[-1]["flags"]


def test_quirks_off_when_gameplay_off(session_factory):
    s = session_factory(10, "silly", gameplay=False)
    s.game.cfg = dict(s.game.cfg, quirks={"chance": 1.0})
    events = s.apply("x", {"actions": PLAN, "say": "", "ok": True})
    assert not any(e["type"] in ("quirk", "forgot") for e in events)


def test_step_limit_fails_level():
    g = Game(6)
    g.steps = g.step_limit - 1
    g.set_plan([{"op": "turn_left"}])
    types = [e["type"] for e in run_to_end(g)]
    assert "level_fail" in types and g.failed == "time_up" and g.steps_left == 0


def test_blackout_reveals_only_nearby_tiles():
    g = Game(9)
    assert g.dark and g.visible(g.pos) and not g.visible((10, 1))
    before = len(g.seen)
    g.set_plan([{"op": "forward", "n": 2}])
    run_to_end(g)
    assert len(g.seen) > before and all(g.visible(p) for p in list(g.seen)[:5])
    assert Game(1).visible((8, 6))       # 一般關卡全亮


def test_limited_vision_and_no_route_hints():
    g9 = Game(9)
    text = describe_world(g9, vision=2)
    assert "看得到" in text or "看不到" in text
    agent = Agent("silly", route_hints=True)
    assert "路線提示" in agent.build_messages(Game(1), "去吸灰塵")[1]["content"]
    assert "路線提示" not in agent.build_messages(Game(6), "去吸灰塵")[1]["content"]


def test_fatigue_lowers_mood_each_command(session_factory):
    s = session_factory(7, "silly")
    m0 = s.mood.value
    s.preprocess("左轉")
    assert s.mood.value == pytest.approx(m0 - LEVELS[7]["fatigue"])


def test_guardrail_disabled_on_hard_levels(session_factory):
    s = session_factory(8)
    assert "壞掉" in handle_slash(s, "/guard on")["say"] and not s.guard_on


def test_modifiers_and_stop_history(session_factory):
    s = session_factory(10)
    icons = {icon for icon, _ in s.modifiers()}
    assert {"🧭", "🙃", "🧠", "💬", "⏱️", "👓", "😪", "🛡️", "🚫", "🏠"} <= icons
    drive(s, "停")
    assert s.history[-1]["kind"] == "stop"


def test_progress_next_level(tmp_path):
    p = Progress(path=tmp_path / "p.json")
    assert p.next_level() == 0
    p.record({"level": 0, "cleared": True, "stars": 3, "score": 1, "n_commands": 1})
    p.record({"level": 1, "cleared": True, "stars": 1, "score": 1, "n_commands": 1})
    assert p.next_level() == 2


def test_route_hints_never_exceed_action_limit():
    """實測 bug：BFS 路線太鋸齒，提示超過 12 個動作 → 模型照抄被判無效 → 一直發呆。"""
    import json
    import re

    from bendan.agent.perception import path_to_actions, route_hints
    from bendan.world.constants import MAX_ACTIONS
    for lv in CAMPAIGN:
        g = Game(lv)
        for x, y in [(x, y) for y in range(g.h) for x in range(g.w) if not g.is_blocked((x, y))][::3]:
            g.pos = (x, y)
            for line in route_hints(g)[1:]:
                acts = json.loads(re.search(r"(\[.*\])", line).group(1))
                assert len(acts) <= MAX_ACTIONS
        g = Game(lv)
        for d in g.dirt:
            route = g.find_route(g.pos, g.facing, d)
            if route:
                assert not any(g.in_forbidden(p) for p in route)
                # 少轉彎的路線動作數不會比 BFS 多太多（多出來的通常是為了繞開樂高之類的危險物）
                assert len(path_to_actions(route, g.facing)) <= len(path_to_actions(g.find_path(g.pos, d), g.facing)) + 2
