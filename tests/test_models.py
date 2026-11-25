"""課程伺服器的三個模型：可以切換、Qwen3 自動 /no_think、跑分頁。"""
from types import SimpleNamespace

import pytest

from bendan import llm
from bendan.evaluation.benchmark import bench_html


class FakeClient:
    def __init__(self, reply):
        self.reply, self.sent = reply, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.sent.append(kw)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))])


@pytest.fixture
def course_server():
    old = (llm.STATE.client, llm.STATE.use_fake, llm.STATE.available_models, llm.STATE.model, llm.STATE.json_mode)
    llm.STATE.use_fake, llm.STATE.available_models, llm.STATE.json_mode = False, ["classroom-llm"], False
    yield
    (llm.STATE.client, llm.STATE.use_fake, llm.STATE.available_models, llm.STATE.model, llm.STATE.json_mode) = old


def test_course_models_can_be_selected_even_if_not_listed(course_server):
    assert llm.on_course_server()
    for m in llm.COURSE_MODELS:
        llm.set_model(m)
        assert llm.STATE.model == m
    with pytest.raises(ValueError):
        llm.set_model("gpt-99")


def test_qwen3_gets_no_think_and_think_block_is_removed(course_server):
    llm.STATE.client = FakeClient('<think>\n\n</think>\n\n{"actions": [], "say": "好"}')
    llm.set_model("qwen3-14b")
    out = llm.chat([{"role": "system", "content": "s"}, {"role": "user", "content": "往前"}])
    assert out == '{"actions": [], "say": "好"}'
    assert llm.STATE.client.sent[-1]["messages"][-1]["content"].endswith("/no_think")
    llm.set_model("llama3.1:8b")
    llm.STATE.client.reply = "沒有思考"
    assert llm.chat([{"role": "user", "content": "往前"}]) == "沒有思考"
    assert not llm.STATE.client.sent[-1]["messages"][-1]["content"].endswith("/no_think")


def test_bench_html_with_and_without_data():
    assert "benchmark_models.py" in bench_html({})
    m = {"model": "qwen2.5:7b", "label": "Qwen2.5 7B",
         "eval": {"format_rate": 0.9, "follow_rate": 0.7, "memory_violation_rate": 0.5, "latency_avg": 1.2},
         "play": {"levels": [0, 1], "pass_rate": 0.75, "per_level": {"0": 1.0, "1": 0.5}, "avg_commands": 8.0,
                  "explosions": 0}}
    m2 = dict(m, model="llama3.1:8b", label="Llama 3.1 8B", eval=dict(m["eval"], follow_rate=0.5))
    html = bench_html({"date": "2026-11-20", "models": [m, m2]})
    assert "Qwen2.5 7B" in html and "Llama 3.1 8B" in html and "70%" in html and "bd-best" in html and "第 1 關" in html


def test_title_screen_has_model_picker_and_bench_button(progress):
    pytest.importorskip("ipywidgets")
    from bendan.ui.widget_mode import WidgetGame
    ui = WidgetGame(0, "serious", tick=0.01, progress=progress, seed=0)
    try:
        assert ui.model_pick in ui.title_screen.children and ui.btn_bench in ui.title_screen.children
        assert ui.model_pick.disabled                      # 離線 FakeLLM：只有一個「大腦」，不能切
        ui.btn_bench.value = True
        assert ui.bench_panel.layout.display == "block" and "跑分" in ui.bench_panel.value
        ui.btn_bench.value = False
        assert ui.bench_panel.layout.display == "none"
    finally:
        ui.quit()


def test_text_mode_cell_does_not_block_run_all():
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "scripts" / "build_notebooks.py").read_text(encoding="utf-8")
    assert 'code(\'# ▶️ 執行這格開始玩（文字模式）\\nsession = bendan.play(mode="silly")' not in src


def test_seed_is_sent_and_dropped_if_the_server_rejects_it(course_server):
    llm.STATE.client = FakeClient('{"actions": [], "say": "好"}')
    llm.set_model("qwen2.5:7b")
    llm.chat([{"role": "user", "content": "往前"}], seed=7)
    assert llm.STATE.client.sent[-1]["seed"] == 7
    llm.chat([{"role": "user", "content": "往前"}])
    assert "seed" not in llm.STATE.client.sent[-1]

    class Rejected(Exception):
        status_code = 400

    old_create = llm.STATE.client._create

    def picky(**kw):
        if "seed" in kw:
            raise Rejected("Unrecognized request argument supplied: seed")
        return old_create(**kw)
    llm.STATE.client.chat.completions.create = picky
    try:
        assert llm.chat([{"role": "user", "content": "往前"}], seed=7) == '{"actions": [], "say": "好"}'
        assert llm.STATE.seed_supported is False and "seed" not in llm.STATE.client.sent[-1]
    finally:
        llm.STATE.seed_supported = True


def test_reply_schema_covers_every_action():
    from bendan.agent.parsing import REPLY_SCHEMA
    from bendan.world.constants import ACTION_WHITELIST
    items = REPLY_SCHEMA["properties"]["actions"]["items"]["anyOf"]
    ops = {items[0]["properties"]["op"]["const"], *items[1]["properties"]["op"]["enum"]}
    assert ops == ACTION_WHITELIST and items[0]["required"] == ["op", "cm"]


def test_structured_output_sends_schema_and_falls_back(course_server):
    """給 schema → response_format json_schema；伺服器不支援範圍關鍵字 → 拿掉再送（json_schema_lite）；對照組不送。"""
    from bendan.agent.parsing import REPLY_SCHEMA
    llm.STATE.client = FakeClient('{"actions": [], "say": "好", "emotion": "普通"}')
    llm.set_model("qwen2.5:7b")
    old_bad = set(llm.STATE.bad_formats)
    try:
        llm.chat([{"role": "user", "content": "往前"}], schema=REPLY_SCHEMA)
        rf = llm.STATE.client.sent[-1]["response_format"]
        assert rf["type"] == "json_schema" and rf["json_schema"]["schema"] == REPLY_SCHEMA
        assert llm.STATE.last_format == "json_schema"

        class Rejected(Exception):
            status_code = 400
        ok_create = llm.STATE.client._create

        def picky(**kw):
            sch = kw.get("response_format", {}).get("json_schema", {}).get("schema")
            if sch is not None and "maximum" in str(sch):
                raise Rejected("unsupported JSON schema feature: maximum")
            return ok_create(**kw)
        llm.STATE.client.chat.completions.create = picky
        llm.chat([{"role": "user", "content": "往前"}], schema=REPLY_SCHEMA)
        assert llm.STATE.last_format == "json_schema_lite" and "json_schema" in llm.STATE.bad_formats
        assert "maximum" not in str(llm.STATE.client.sent[-1]["response_format"])
        with llm.structured_output(False):
            llm.chat([{"role": "user", "content": "往前"}], schema=REPLY_SCHEMA)
        assert "response_format" not in llm.STATE.client.sent[-1] and llm.STATE.last_format == "plain"
    finally:
        llm.STATE.bad_formats = old_bad


def test_agent_records_the_output_format():
    from bendan.agent import Agent
    from bendan.world import Game
    assert Agent("silly").think(Game(1), "往前")["format"] == "fake"
