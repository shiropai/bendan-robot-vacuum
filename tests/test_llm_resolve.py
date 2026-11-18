from bendan.llm.client import resolve_model


def test_resolve_course_alias_to_local_model_names():
    local = ["mlx-community/Qwen2.5-7B-Instruct-4bit", "mlx-community/Qwen2.5-3B-Instruct-4bit"]
    assert resolve_model("qwen2.5:7b", local) == "mlx-community/Qwen2.5-7B-Instruct-4bit"
    assert resolve_model("qwen2.5:3b", local) == "mlx-community/Qwen2.5-3B-Instruct-4bit"
    assert resolve_model("llama3.1:8b", local) is None
    course = ["classroom-llm", "llama3.1:8b", "qwen2.5:3b", "qwen2.5:7b"]
    assert resolve_model("qwen2.5:7b", course) == "qwen2.5:7b"
    assert resolve_model("anything", []) == "anything"
