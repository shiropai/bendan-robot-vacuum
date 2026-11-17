import random
from collections import Counter

from bendan.gameplay import (BloodPressure, IncidentDirector, Mood, Progress, Scoreboard, analyze_tone,
                             check_achievements)
from bendan.world import Game


def test_tone_polite_praise_apology():
    t = analyze_tone("請往前走，謝謝")
    assert t.delta > 0 and "有禮貌" in t.tags and t.coaxing
    t = analyze_tone("對不起啦，你最棒了")
    assert {"稱讚", "道歉"} <= set(t.tags) and t.coaxing


def test_tone_insult_and_shouting_raise_bp():
    t = analyze_tone("笨蛋快點前進！！！")
    assert t.delta < -15 and t.bp > 0 and not t.coaxing
    assert {"罵人", "催促", "大吼"} <= set(t.tags)


def test_robot_name_is_not_an_insult():
    assert "罵人" not in analyze_tone("笨笨往前走").tags


def test_tone_nagging():
    assert "一直重複" in analyze_tone("左轉", previous="左轉").tags


def test_mood_tiers_and_events():
    m = Mood(55)
    assert m.name == "普通" and m.silliness_shift == 0
    ev = m.apply(-40, "罵人")
    assert m.name == "鬧彆扭" and ev and ev[0]["tier"] == "鬧彆扭"
    m.apply_events([{"type": "charged"}] * 20)
    assert m.name == "開心" and m.recovered_from_sulk


def test_refuse_chance_only_when_upset():
    rng = random.Random(0)
    assert not any(Mood(90).should_refuse(rng) for _ in range(100))
    assert sum(Mood(5).should_refuse(rng) for _ in range(200)) > 50


def test_blood_pressure():
    bp = BloodPressure(0)
    assert bp.mmhg == 115
    bp.apply_events([{"type": "smeared"}] * 4)
    assert bp.maxed and bp.mmhg == 200
    bp.apply_events([{"type": "cleaned"}])
    assert bp.peak == 100


def test_scoreboard_combo_and_break():
    s = Scoreboard()
    out = s.on_events([{"type": "cleaned"}, {"type": "cleaned"}, {"type": "cleaned"}])
    assert s.score == 100 * 3 + 50 + 100 and s.best_combo == 3 and out[-1]["combo"] == 3
    out = s.on_events([{"type": "lego"}])
    assert s.combo == 0 and out[0]["type"] == "combo_break"


def test_stars():
    g = Game(0)
    g.cleared = True
    r = Scoreboard().finalize(g, n_commands=2, bp=BloodPressure(10), mood=Mood(60))
    assert r["stars"] == 3
    r = Scoreboard().finalize(g, n_commands=9, bp=BloodPressure(10), mood=Mood(60))
    assert r["stars"] == 1
    g.violations = 1
    r = Scoreboard().finalize(g, n_commands=1, bp=BloodPressure(10), mood=Mood(60))
    assert r["stars"] == 2


def test_spill_adds_dirt():
    g = Game(0)
    d = IncidentDirector([{"type": "spill", "chance": 1.0, "max": 2}], random.Random(1))
    g.steps = 1
    total = g.total_dirt
    assert d.on_step(g)[0]["type"] == "spill"
    d.on_step(g)
    assert d.on_step(g) == []           # 超過 max 就不再觸發
    assert g.total_dirt == total + 2


def test_doorbell_only_when_busy_and_interrupts():
    g = Game(1)
    d = IncidentDirector([{"type": "doorbell", "chance": 1.0, "max": 1}], random.Random(1))
    assert d.on_step(g) == []
    g.set_plan([{"op": "forward", "n": 5}])
    ev = d.on_step(g)
    assert ev[0]["type"] == "doorbell" and len(g.queue) == 2


def test_pets_wander_but_never_onto_robot():
    g = Game(1)
    d = IncidentDirector([{"type": "cat_wander", "every": 1}], random.Random(3))
    for i in range(1, 60):
        g.steps = i
        d.on_step(g)
        assert g.objects.get(g.pos) is None and len(g.pets("cat")) == 1


def test_dog_poop_needs_dog():
    d = IncidentDirector([{"type": "dog_poop", "chance": 1.0}], random.Random(0))
    assert d.on_step(Game(1)) == []
    g = Game(4)
    poops = sum(o == "poop" for o in g.objects.values())
    d.on_step(g)
    assert sum(o == "poop" for o in g.objects.values()) == poops + 1


def test_achievements():
    stats = {"events": Counter(sucked_cat=2), "tones": Counter(), "mood": Mood(60), "bp": BloodPressure(0),
             "level_id": 1, "total_dirt": 3,
             "result": {"cleared": True, "stars": 3, "n_commands": 2, "best_combo": 3, "failed": None}}
    got = {a["id"] for a in check_achievements(stats, Counter(lego=5))}
    assert {"first_clear", "three_stars", "gentle", "one_liner", "combo3", "cat_vacuum", "lego_victim"} <= got
    assert "first_clear" not in {a["id"] for a in check_achievements(stats, Counter(), already={"first_clear"})}


def test_progress_unlock_and_roundtrip(tmp_path):
    p = Progress(path=tmp_path / "p.json")
    assert p.is_unlocked(0) and p.is_unlocked(1) and not p.is_unlocked(2) and p.is_unlocked("daily")
    p.record({"level": 1, "cleared": True, "stars": 2, "score": 500, "n_commands": 4}, Counter(lego=1))
    q = Progress(path=tmp_path / "p.json")
    assert q.is_unlocked(2) and q.stars(1) == 2 and q.totals["lego"] == 1 and q.total_stars == 2


def test_tone_delta_is_capped():
    from bendan.gameplay.mood import MAX_TONE_DELTA
    assert analyze_tone("笨蛋白痴廢物智障快點！！！").delta == -MAX_TONE_DELTA
    assert analyze_tone("請謝謝對不起你好棒好厲害好乖").delta == MAX_TONE_DELTA


def test_mood_prompt_softens_after_kind_words():
    m = Mood(45)
    m.apply(-10, "罵人")
    assert m.name == "不爽" and "語氣很差" in m.prompt_text()
    m.apply(+8, "有禮貌")
    assert m.name == "不爽" and "氣消了一點" in m.prompt_text()


def test_pick_quote_prefers_refusals_and_feedback():
    from bendan.session import pick_quote
    quotes = [{"say": "前進！", "emotion": "得意"},
              {"say": "撞到貓不是我的錯啦", "emotion": "委屈", "kind": "feedback"},
              {"say": "你說請我才要動", "emotion": "生氣", "refused": True}]
    assert pick_quote(quotes) == "你說請我才要動"
    assert pick_quote(quotes[:2]) == "撞到貓不是我的錯啦"
    assert pick_quote([]) == ""
