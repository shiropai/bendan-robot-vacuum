"""LLM 連線層：課程 OpenAI-compatible API ＋ 離線 FakeLLM。"""
from .client import STATE, chat, connect, latency_test, list_models, model_name, set_model, using_model
from .fake import FakeLLM, parse_simple_command

__all__ = ["FakeLLM", "STATE", "chat", "connect", "latency_test", "list_models", "model_name",
           "parse_simple_command", "set_model", "using_model"]
