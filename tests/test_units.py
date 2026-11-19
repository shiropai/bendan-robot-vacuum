"""真實單位：1 格 = 50 公分；玩家和 LLM 看到的距離都是公分／公尺。"""
import json

import pytest

from bendan.agent.parsing import validate_output
from bendan.agent.perception import describe_world, route_hints, scan
from bendan.world import Game
from bendan.world.units import cells_from_cm, fmt_len, parse_length_cells


@pytest.mark.parametrize("cells,text", [(1, "50 公分"), (2, "1 公尺"), (3, "1.5 公尺"), (10, "5 公尺")])
def test_fmt_len(cells, text):
    assert fmt_len(cells) == text


@pytest.mark.parametrize("cm,cells", [(50, 1), (100, 2), (150, 3), (30, 1), (74, 1), (76, 2), (0, None), (-5, None), ("x", None)])
def test_cells_from_cm(cm, cells):
    assert cells_from_cm(cm) == cells


@pytest.mark.parametrize("text,cells", [("往前走1.5公尺", 3), ("前進五十公分", 1), ("往前走一公尺然後吸", 2), ("走三格", 3),
                                        ("前進兩米", 4), ("往前 100 cm", 2), ("前進一百五十公分", 3), ("往前走一點五公尺", 3),
                                        ("往前走", None)])
def test_parse_length_cells(text, cells):
    assert parse_length_cells(text) == cells


def test_parser_accepts_cm_m_and_legacy_cells():
    plan, err = validate_output({"actions": [{"op": "forward", "cm": 150}, {"op": "forward", "m": 1},
                                             {"op": "forward", "n": 2}], "say": "好"})
    assert not err and [a["n"] for a in plan["actions"]] == [3, 2, 2]
    plan, err = validate_output({"actions": [{"op": "forward", "cm": 0}], "say": "好"})
    assert plan is None and err


def test_world_description_uses_meters_not_cells():
    g = Game(3)
    text = describe_world(g, hints=True)
    assert "公尺" in text or "公分" in text
    assert " 格" not in text and "格內" not in text
    assert "再往前就會撞到" in scan(g, g.facing) or "更遠處" in scan(g, g.facing)
    hint = route_hints(g)[-1]
    acts = json.loads(hint.split("：", 1)[1])
    assert all("cm" in a and a["cm"] % 50 == 0 for a in acts if a["op"] == "forward")
