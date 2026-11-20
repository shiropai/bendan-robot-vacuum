"""LLM 連線層：課程 OpenAI-compatible API ＋ 離線 FakeLLM。"""
from .client import (COURSE_MODELS, STATE, chat, connect, is_qwen3, latency_test, list_models, model_name,
                     on_course_server, set_model, using_model)
from .fake import FakeLLM, parse_simple_command

__all__ = ["COURSE_MODELS", "FakeLLM", "STATE", "chat", "connect", "is_qwen3", "latency_test", "list_models",
           "model_name", "on_course_server", "parse_simple_command", "set_model", "using_model"]
