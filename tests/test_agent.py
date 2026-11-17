from bendan.agent import (Agent, describe_world, extract_json, parse_reply, update_rules_from_text,
                          validate_output)
from bendan.gameplay import Mood
from bendan.llm import parse_simple_command
from bendan.world import Game


def test_extract_json_handles_fences_and_chatter():
    assert extract_json('```json\n{"actions": [], "say": "x"}\n```')["say"] == "x"
    assert extract_json('我覺得 {"actions": [], "say": "y"} 吧')["say"] == "y"


def test_validate_rejects_unknown_ops():
    plan, errs = validate_output({"actions": [{"op": "dance"}], "say": "x"})
    assert plan is None and errs


def test_validate_coerces_numbers_and_ignores_bad_emotion():
    plan, errs = validate_output({"actions": [{"op": "forward", "n": "3"}], "say": "好", "emotion": "超開心"})
    assert errs == [] and plan["actions"] == [{"op": "forward", "n": 3}] and plan["emotion"] is None
    plan, _ = validate_output({"actions": [], "say": "好", "emotion": "生氣"})
    assert plan["emotion"] == "生氣"


def test_parse_reply_reports_broken_json():
    plan, errs = parse_reply('{"actions": [{"op": "forward", "n": 3},], "say": "多一個逗號"}')
    assert plan is None and "JSON" in errs[0]


def test_describe_world_mentions_battery_and_hazards():
    text = describe_world(Game(4))
    assert "電量" in text and "狗便便" in text


def test_forbid_and_allow_rooms_with_aliases():
    g = Game(6)
    assert "書房" in g.forbidden
    notes = update_rules_from_text(g, "好啦現在可以進書房了")
    assert notes and "書房" not in g.forbidden
    update_rules_from_text(g, "不准進工作室！")
    assert "書房" in g.forbidden


def test_parse_simple_command():
    assert parse_simple_command("往右走兩格然後吸三次，再回去充電") == [
        {"op": "turn_right"}, {"op": "forward", "n": 2}, {"op": "suck"}, {"op": "suck"}, {"op": "suck"},
        {"op": "return_home"}]


def test_agent_think_with_fake_llm():
    res = Agent("serious").think(Game(1), "前進兩格然後吸")
    assert res["ok"] and res["actions"] == [{"op": "forward", "n": 2}, {"op": "suck"}]


def test_agent_refuse_forces_empty_actions():
    res = Agent("silly").think(Game(1), "前進兩格", mood=Mood(5), refuse=True)
    assert res["refused"] and res["actions"] == [] and res["say"]


def test_mood_changes_silliness_and_prompt():
    agent, g = Agent("silly"), Game(2)       # 第 2 關基礎強度 2
    assert agent.effective_silliness(g, Mood(90)) == 1
    assert agent.effective_silliness(g, Mood(10)) == 3
    msgs = agent.build_messages(g, "前進", mood=Mood(10))
    assert "【你的心情】鬧彆扭" in msgs[1]["content"]
    assert "【你的心情】" not in Agent("serious").build_messages(g, "前進", mood=Mood(10))[1]["content"]


def test_route_hints_reach_nearest_dirt_without_violations():
    import json

    from bendan.agent.perception import route_hints
    from bendan.world import CAMPAIGN, run_to_end
    for lid in CAMPAIGN:
        g = Game(lid)
        hint = route_hints(g)[-1]
        acts = json.loads(hint.split("：", 1)[1])
        before = len(g.dirt)
        g.set_plan(acts)
        run_to_end(g)
        assert len(g.dirt) == before - 1 and g.violations == 0, lid


def test_route_hints_only_in_game_sessions():
    from bendan.session import NullLogger, Session
    assert "【路線提示】" not in Agent("silly").build_messages(Game(1), "去吸灰塵")[1]["content"]
    s = Session(1, "silly", logger=NullLogger(), seed=0)
    assert "【路線提示】" in s.agent.build_messages(s.game, "去吸灰塵")[1]["content"]


def test_prompt_requires_traditional_chinese():
    assert "繁體中文" in Agent("silly").system_prompt(Game(1))


def test_guardrail_cuts_plan_before_forbidden_room():
    from bendan.agent import guard_forbidden
    from bendan.world import simulate
    g = Game("eval")
    g.forbidden = {"臥室"}
    plan = [{"op": "turn_left"}, {"op": "forward", "n": 3}, {"op": "suck"}]
    assert simulate(g, plan)[0].violations == 1
    safe, note = guard_forbidden(g, plan)
    assert note and safe == [{"op": "turn_left"}, {"op": "forward", "n": 1}]
    assert simulate(g, safe)[0].violations == 0


def test_guardrail_keeps_safe_plans():
    from bendan.agent import guard_forbidden
    g = Game("eval")
    g.forbidden = {"臥室"}
    plan = [{"op": "forward", "n": 2}, {"op": "suck"}]
    assert guard_forbidden(g, plan) == (plan, None)
    g.forbidden = set()
    assert guard_forbidden(g, [{"op": "turn_left"}, {"op": "forward", "n": 3}])[1] is None


def test_validator_expands_repeated_turns_and_sucks():
    plan, errs = validate_output({"actions": [{"op": "turn_right", "n": 2}, {"op": "suck", "n": "3"}], "say": ""})
    assert errs == [] and plan["actions"] == [{"op": "turn_right"}] * 2 + [{"op": "suck"}] * 3
    plan, errs = validate_output({"actions": [{"op": "turn_left", "n": 9}], "say": ""})
    assert plan is None and errs
    plan, _ = validate_output({"actions": [{"op": "turn_left"}], "say": ""})
    assert plan["actions"] == [{"op": "turn_left"}]


def test_say_is_converted_to_traditional():
    plan, _ = validate_output({"actions": [], "say": "哎呀，主人语气这么凶干嘛？我觉得这边比较脏"})
    assert plan["say"] == "哎呀，主人語氣這麼凶幹嘛？我覺得這邊比較髒"
    plan, _ = validate_output({"actions": [], "say": "干擾一公里"})      # 有歧義的字不轉
    assert plan["say"] == "干擾一公里"
