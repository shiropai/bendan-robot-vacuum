"""提示詞池：每句抽幾段「今天的笨笨」，越後面的關卡越常抽到會影響動作的段落。"""
import random

from bendan.agent import Agent
from bendan.agent.flavor import CHAOS, HABITS, LEVEL_FLAVOR, MOODLETS, pick_flavor
from bendan.world import Game


def test_pools_are_big_and_unique():
    assert len(MOODLETS) >= 30 and len(HABITS) >= 20 and len(CHAOS) >= 15
    assert len(set(MOODLETS + HABITS + CHAOS)) == len(MOODLETS + HABITS + CHAOS)


def rates(level, n=400):
    g, rng = Game(level), random.Random(0)
    picks = [pick_flavor(g, rng)[1] for _ in range(n)]
    return sum(bool(p["habit"]) for p in picks) / n, sum(bool(p["chaos"]) for p in picks) / n


def test_later_levels_get_more_mischief():
    assert rates(0) == (0.0, 0.0)
    h3, c3 = rates(3)
    h10, c10 = rates(10)
    assert 0 < c3 < c10 and h3 < h10
    assert all(LEVEL_FLAVOR[a]["chaos_p"] <= LEVEL_FLAVOR[a + 1]["chaos_p"] for a in range(10))


def test_flavor_goes_into_prompt_only_in_gameplay_silly_mode():
    g = Game(10)
    on = Agent("silly", seed=1, flavor=True).build_messages(g, "往前")[1]["content"]
    off = Agent("silly", seed=1).build_messages(g, "往前")[1]["content"]
    serious = Agent("serious", seed=1, flavor=True).build_messages(g, "往前")[1]["content"]
    assert "【今天的笨笨】" in on and "【今天的笨笨】" not in off and "【今天的笨笨】" not in serious


def test_same_seed_same_flavor():
    g = Game(7)
    a = [pick_flavor(g, random.Random(5))[0] for _ in range(2)]
    assert a[0] == a[1]
