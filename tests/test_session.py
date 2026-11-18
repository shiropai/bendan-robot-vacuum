import json

from conftest import drive

from bendan.session import JsonlLogger
from bendan.ui.commands import handle_slash


def test_clear_tutorial_level(session_factory, progress):
    s = session_factory(0, "serious")
    drive(s, "請往前走三格然後吸")
    events = drive(s, "謝謝！請右轉走兩格再左轉，然後吸")
    types = [e["type"] for e in events]
    assert "level_clear" in types and "level_result" in types
    assert s.result["cleared"] and s.result["stars"] == 3
    assert progress.stars(0) == 3 and "first_clear" in progress.unlocked_achievements


def test_stop_is_local(session_factory):
    s = session_factory(1)
    pre = s.preprocess("停！")
    assert pre["handled"] and pre["events"][-1]["type"] == "stopped"


def test_insults_make_robot_sulk_and_refuse(session_factory):
    s = session_factory(1, "silly")
    for _ in range(4):
        drive(s, "笨蛋 白痴 快點左轉")
    assert s.mood.name == "鬧彆扭"
    refused = sum(s.preprocess("廢物 左轉")["refuse"] for _ in range(30))
    assert refused > 3


def test_polite_words_prevent_refusal(session_factory):
    s = session_factory(1, "silly")
    s.mood.value = 0
    assert not any(s.preprocess("請左轉")["refuse"] for _ in range(30))


def test_blood_pressure_failure(session_factory):
    s = session_factory(1)
    s.bp.value = 99
    s.game.set_plan([{"op": "turn_left"}, {"op": "forward", "n": 9}])
    events = []
    while s.busy() or not events:
        events += s.tick()
        if s.game.over:
            break
    assert s.game.failed == "owner_faint"
    assert "bp_max" in {a["id"] for a in s.new_achievements}


def test_command_limit_failure(session_factory):
    s = session_factory(6)
    for _ in range(s.command_limit):
        drive(s, "左轉")
    assert not s.game.over and s.commands_left() == 0
    pre = s.preprocess("左轉")
    assert pre["handled"] and s.game.failed == "time_up" and s.result["stars"] == 0


def test_gameplay_off_is_original_behaviour(session_factory):
    s = session_factory(1, "silly", gameplay=False)
    events = drive(s, "笨蛋 前進兩格")
    assert not any(e["type"] in ("tone", "mood", "pet_moved") for e in events)
    assert s.mood.value == 65


def test_feedback_loop_runs_after_interrupt(session_factory):
    s = session_factory(1, "serious", feedback_rounds=1)
    s.agent.memory.recent.clear()
    drive(s, "左轉然後前進九格")       # 撞牆 → 回饋給 LLM
    assert any(r["cmd"].startswith("（修正）") for r in s.agent.memory.recent)


def test_logger_writes_jsonl(tmp_path, progress):
    from bendan.session import Session
    log = tmp_path / "log.jsonl"
    s = Session(0, "serious", logger=JsonlLogger(log), progress=progress, seed=0)
    drive(s, "請往前走三格然後吸")
    rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    assert rows and rows[0]["kind"] == "command" and "mood" in rows[0] and "bp_mmhg" in rows[0]


def test_slash_commands(session_factory, progress):
    s = session_factory(1)
    assert handle_slash(s, "前進") is None
    assert handle_slash(s, "/level 4")["changed"] and s.game.level_id == 4
    assert handle_slash(s, "/next")["changed"] and s.game.level_id == 5
    assert handle_slash(s, "/level daily")["changed"] and s.game.level_id == "daily"
    progress.unlock_all = False
    out = handle_slash(s, "/level 6")
    assert not out["changed"] and "🔒" in out["say"]
    assert "成就" in handle_slash(s, "/achievements")["html"]


def test_session_guardrail_and_slash_toggle(session_factory):
    s = session_factory(2, "serious")          # 第 2 關：臥室是禁區
    assert "開啟" in handle_slash(s, "/guard on")["say"] and s.guardrail
    s.game.pos, s.game.facing = (7, 3), 1      # 臥室門口，面向東
    events = s.apply("衝進臥室", {"actions": [{"op": "forward", "n": 3}], "say": "衝！", "ok": True})
    while s.busy():
        events += s.tick()
    assert any(e["type"] == "guardrail" for e in events) and s.game.violations == 0
    handle_slash(s, "/guard off")
    assert not s.guardrail


def test_go_home_sentence_is_handled_locally(session_factory):
    """整句只是「回充電座」：不問 LLM，直接自動導航回家（跟「停」一樣是保底）。"""
    s = session_factory(1, "silly")
    s.game.pos, s.game.facing, s.game.battery = (5, 5), 0, 40
    pre = s.preprocess("請回充電座")
    assert pre["handled"] and s.game.queue
    while s.busy():
        s.tick()
    assert s.game.pos == s.game.home and s.game.battery == s.game.battery_max
    assert s.history[-1]["cmd"] == "請回充電座" and s.history[-1]["kind"] == "home"
    assert not s.preprocess("先往前走兩格再回充電座")["handled"]     # 有其他動作的句子還是交給 LLM
