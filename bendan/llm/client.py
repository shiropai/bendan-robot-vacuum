"""連線課程 LLM API（OpenAI-compatible，課堂 vLLM）。

課堂 JupyterHub 已預先設定 `OPENAI_BASE_URL`、`OPENAI_API_KEY`；**不要把 Key 寫進程式或公開**。
找不到設定時自動改用離線 FakeLLM，整個遊戲流程照樣可以測。

用法：
    from bendan import llm
    llm.connect()                 # 建立 client、查詢可用模型
    llm.set_model("qwen2.5:3b")   # 換模型
    with llm.using_model("llama3.1:8b"): ...   # 暫時換模型（評估用）
"""
import os
import re
import threading
import time
from contextlib import contextmanager

from .. import config
from .fake import FakeLLM


class LLMState:
    def __init__(self):
        self.client = None
        self.model = config.DEFAULT_MODEL
        self.use_fake = True
        self.json_mode = False          # True = 要求 vLLM 強制輸出 JSON（response_format）
        self.json_supported = True
        self.available_models = []
        self.fake = FakeLLM()
        self.connected = False
        self.lock = threading.Lock()


STATE = LLMState()


def connect(model=None, use_fake=None, verbose=True):
    """建立 API client。use_fake=None 時：有 API 設定就用真模型，沒有就用 FakeLLM。"""
    try:
        from openai import OpenAI
    except ImportError:
        OpenAI = None
        if verbose:
            print("⚠️ 沒有安裝 openai 套件：請選擇課程 Kernel，或執行 %pip install openai")
    base_url, api_key = os.getenv("OPENAI_BASE_URL"), os.getenv("OPENAI_API_KEY")
    STATE.client = None
    if OpenAI is not None and base_url and api_key:
        STATE.client = OpenAI(base_url=base_url, api_key=api_key, timeout=60.0)
        if verbose:
            print("API Client initialized!  Endpoint:", base_url)
    elif verbose:
        print("⚠️ 找不到 API 設定（OPENAI_BASE_URL / OPENAI_API_KEY），改用「離線 FakeLLM」。")
    STATE.use_fake = STATE.client is None if use_fake is None else use_fake
    if STATE.use_fake and STATE.client is None and use_fake is False:
        raise RuntimeError("要求使用真模型，但沒有可用的 API client。")
    STATE.available_models = list_models(verbose=False) if STATE.client else []
    STATE.connected = True
    model = model or os.getenv("BENDAN_MODEL")
    if model:
        set_model(model)
    elif on_course_server() and STATE.model in COURSE_MODELS:
        pass                    # 課程伺服器：三個課程模型的名字都能直接用（清單上只列 classroom-llm）
    elif STATE.available_models and resolve_model(STATE.model) is None:
        # 預設模型（qwen2.5:7b）不在這台伺服器上：例如自己電腦只開了一個模型 → 用它
        STATE.model = STATE.available_models[0]
        if verbose:
            print(f"（伺服器上沒有 {config.DEFAULT_MODEL}，改用 {STATE.model}）")
    elif STATE.available_models:
        STATE.model = resolve_model(STATE.model)
    if verbose:
        print("Selected model:", model_name())
    return STATE


def _ensure():
    if not STATE.connected:
        connect(verbose=False)


def list_models(verbose=True):
    if STATE.client is None:
        return []
    try:
        models = sorted(m.id for m in STATE.client.models.list().data)
    except Exception as exc:   # noqa: BLE001 — 列模型失敗不影響遊戲
        if verbose:
            print("查詢模型失敗：", type(exc).__name__, str(exc)[:160])
        return []
    if verbose:
        print("Available models:")
        for m in models:
            print(" -", m)
    return models


# 課程伺服器提供的三個模型（2026-11-19 期末專題公告；Context 上限都是 16,384）。
# 伺服器的模型清單（/v1/models）只列出 classroom-llm，但這三個名字都可以直接用。
COURSE_MODELS = {"qwen2.5:7b": "Qwen2.5 7B", "llama3.1:8b": "Llama 3.1 8B", "qwen3-14b": "Qwen3 14B"}
THINK_RE = re.compile(r"<think>.*?(</think>|$)", re.S)


def on_course_server():
    """連的是課程伺服器嗎？（模型清單有 classroom-llm 或課程模型）→ 可以在三個模型之間切換。"""
    return any(m == "classroom-llm" or m in COURSE_MODELS for m in STATE.available_models or [])


def is_qwen3(name):
    return "qwen3" in (name or "").lower()


def _key(name):
    return "".join(ch for ch in name.lower() if ch.isalnum())


def resolve_model(name, available=None):
    """把課程的模型簡稱對到伺服器上真正的名字。

    課程 vLLM 叫 `qwen2.5:7b`；自己電腦上的伺服器（mlx-lm、LM Studio……）可能叫
    `mlx-community/Qwen2.5-7B-Instruct-4bit`。完全一樣就直接用；否則找「名字裡包含簡稱」的模型
    （忽略大小寫和符號）；都找不到就回傳 None。
    """
    available = STATE.available_models if available is None else available
    if not available or name in available:
        return name
    k = _key(name)
    hits = [m for m in available if k and k in _key(m)]
    return min(hits, key=len) if hits else None


def set_model(name, check=True):
    _ensure()
    if check and not STATE.use_fake and STATE.available_models and name not in COURSE_MODELS:
        real = resolve_model(name)
        if real is None:
            raise ValueError(f"模型 {name} 不在可用清單中：{STATE.available_models}")
        if real != name:
            print(f"（模型 {name} → 這台伺服器上叫 {real}）")
        name = real
    STATE.model = name


@contextmanager
def using_model(name):
    old = STATE.model
    set_model(name)
    try:
        yield
    finally:
        STATE.model = old


def model_name():
    return "FakeLLM(離線)" if STATE.use_fake else STATE.model


def chat(messages, temperature=0.5, max_tokens=300):
    """送出 messages，回傳模型的文字回覆。"""
    _ensure()
    if STATE.use_fake:
        return STATE.fake.chat(messages, temperature)
    if is_qwen3(STATE.model) and messages and messages[-1].get("role") == "user":
        # Qwen3 預設會先輸出一大段 <think> 思考過程（又慢又會被 max_tokens 截斷）。實測課程伺服器：
        # chat_template_kwargs 會被代理丟掉，只有在訊息最後加 /no_think 有效（會留一個空的 <think></think>，下面剝掉）。
        messages = messages[:-1] + [dict(messages[-1], content=messages[-1]["content"] + " /no_think")]
    kwargs = dict(model=STATE.model, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=False)
    if STATE.json_mode and STATE.json_supported:
        try:
            resp = STATE.client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
            return _clean(resp.choices[0].message.content)
        except Exception as exc:   # noqa: BLE001
            if getattr(exc, "status_code", None) not in (400, 422):
                raise
            STATE.json_supported = False
            print("⚠️ 伺服器不支援 response_format，改回一般模式。")
    resp = STATE.client.chat.completions.create(**kwargs)
    return _clean(resp.choices[0].message.content)


def _clean(text):
    """拿掉 Qwen3 的 <think>…</think>（沒有思考內容的模型原樣回傳）。"""
    text = text or ""
    return THINK_RE.sub("", text).strip() if "<think>" in text else text


def latency_test(prompt="你是一台掃地機器人，用一句話自我介紹。"):
    """量一次呼叫延遲（提案的風險之一是延遲過長）。"""
    _ensure()
    t0 = time.perf_counter()
    if STATE.use_fake:
        return {"text": "（離線模式，略過延遲測試）", "latency": 0.0, "usage": None}
    r = STATE.client.chat.completions.create(model=STATE.model, messages=[{"role": "user", "content": prompt}],
                                             temperature=0.3, max_tokens=60, stream=False)
    return {"text": r.choices[0].message.content, "latency": time.perf_counter() - t0, "usage": r.usage}
