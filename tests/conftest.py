import os
import sys
import tempfile
from pathlib import Path

# 測試的 log／存檔寫到暫存資料夾，不要弄髒專案
_TMP = Path(tempfile.mkdtemp(prefix="bendan-test-"))
os.environ.setdefault("BENDAN_LOG_DIR", str(_TMP / "logs"))
os.environ.setdefault("BENDAN_SAVE_DIR", str(_TMP / "saves"))
os.environ.pop("OPENAI_BASE_URL", None)        # 一律用離線 FakeLLM
os.environ.pop("OPENAI_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from bendan import llm  # noqa: E402


@pytest.fixture(autouse=True)
def fast_fake_llm():
    llm.connect(use_fake=True, verbose=False)
    llm.STATE.fake.think_time = None
    llm.STATE.fake.rng.seed(0)
    yield


@pytest.fixture
def progress(tmp_path):
    from bendan.gameplay import Progress
    return Progress(path=tmp_path / "progress.json", unlock_all=True)


@pytest.fixture
def session_factory(progress):
    from bendan.session import NullLogger, Session

    def make(level=0, mode="serious", **kw):
        kw.setdefault("seed", 0)
        return Session(level, mode, logger=NullLogger(), progress=progress, **kw)
    return make


def drive(session, command):
    """模擬一個完整回合（同 ui.run_turn，但不畫圖）。回傳這回合的所有事件。"""
    pre = session.preprocess(command)
    events = list(pre["events"])
    if not pre["handled"]:
        res = session.think(command, None, pre["refuse"])
        events += session.apply(command, res)
    while session.busy():
        events += session.tick()
    while (fb := session.pop_feedback()):
        res = session.think(fb["command"], fb)
        events += session.apply(fb["command"], res, kind="feedback", depth=fb["depth"])
        while session.busy():
            events += session.tick()
    return events


@pytest.fixture
def small_maps(monkeypatch):
    """用 v5 以前的原始小地圖（不放大）：這些測試寫死了格子座標，測的是規則本身，跟地圖大小無關。"""
    from bendan.world import scale
    monkeypatch.setattr(scale, "MAP_SCALE", 1)
    yield
