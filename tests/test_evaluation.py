from bendan.evaluation import (TEST_SET, normalize, plot_mood_eval, plot_summary, run_eval, run_mood_eval,
                               short_to_actions, summarize_eval, summarize_mood_eval)
from bendan.render import hud_html, render_ascii


def test_normalize_equivalences():
    assert normalize(short_to_actions("LL F2")) == normalize(short_to_actions("RR F2")) == "R R F2"
    assert normalize(short_to_actions("F2 F1")) == "F3"
    assert normalize(short_to_actions("RRR")) == "L"


def test_run_eval_with_fake_llm():
    df = run_eval(modes=("serious",), verbose=False, save=False)
    s = summarize_eval(df)
    assert len(df) == len(TEST_SET) + 6
    assert 0.5 <= s["照做率"].iloc[0] <= 1 and 0 <= s["記憶遵守率"].iloc[0] <= 1
    assert plot_summary(s, show=False)[:4] == b"\x89PNG"


def test_mood_eval_with_fake_llm():
    df = run_mood_eval(tests=TEST_SET[:10], verbose=False, save=False)
    s = summarize_mood_eval(df)
    assert list(s.index) == ["開心", "普通", "不爽", "鬧彆扭"]
    assert plot_mood_eval(s, show=False)[:4] == b"\x89PNG"


def test_renderers(session_factory):
    s = session_factory(4, "silly")
    s.game.fail("owner_faint", "x")
    assert "G" in render_ascii(s.game)
    assert "主人血壓" in hud_html(s, "hi", [{"type": "lego", "msg": "痛"}])


def test_emoji_map_fallback_and_env_check():
    import bendan
    from bendan.render import map_html
    from bendan.world import Game
    html = map_html(Game(4))
    assert "➡️" in html and "💩" in html and "🐶" in html
    env = bendan.check_env(verbose=False)
    assert set(env) == {"missing", "api"}
