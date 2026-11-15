"""Per-node LLM routing, token/cost accounting and deterministic fallback.

`get_llm(node)` returns a LangChain chat model configured from agent/config.yaml (or None when the
provider is `heuristic`). `call_llm(node, prompt, variables)` is what nodes use: it renders the
prompt, calls the model (falling back to the cheaper model on error) and returns an `LLMResult`; on
any failure it returns `ok=False` so the node takes its deterministic path.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.prompts import render_prompt
from agent.settings import cfg

_lock = threading.Lock()
USAGE_TOTALS: dict[str, dict[str, float]] = {}


@dataclass
class LLMResult:
    ok: bool
    text: str = ""
    data: Any = None
    model: str = "heuristic"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    fallback_used: bool = False
    error: Optional[str] = None
    prompt_version: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def usage(self) -> dict:
        return {"tokens": self.tokens_in + self.tokens_out, "cost_usd": self.cost_usd}


def provider_name() -> str:
    env = os.environ.get("LLM_PROVIDER")
    if env:
        return env.lower()
    return "profile"


def node_config(node: str) -> dict:
    """Resolve the model config for a node: profile → node, then deploy override from LLM_PROVIDER."""
    profile = os.environ.get("GIGBID_PROFILE") or cfg("profile", default="open")
    prof = cfg("profiles", profile, default={}) or {}
    conf = dict((prof.get("nodes") or {}).get(node) or prof.get("defaults") or {})
    prov = provider_name()
    if prov not in ("profile", ""):
        ov = cfg("deploy_overrides", prov, default=None)
        if ov is None:
            ov = {"provider": prov}
        ov = dict(ov)
        conf["provider"] = ov.get("provider", conf.get("provider"))
        if ov.get("provider") == "openai_compat":
            strong = node in (cfg("node_groups", "strong", default=[]) or [])
            conf["model"] = ov["strong_model"] if strong else ov["cheap_model"]
            conf["base_url_env"] = ov.get("base_url_env")
            conf["base_url_default"] = ov.get("base_url_default")
            conf["api_key_env"] = ov.get("api_key_env")
            conf["timeout_s"] = ov.get("timeout_s", conf.get("timeout_s", 60))
            for k in ("max_tokens", "reasoning_effort"):
                if ov.get(k):
                    conf[k] = ov[k]
            if ov.get("fallback_model") and ov["fallback_model"] != conf["model"]:
                conf["fallback"] = {"provider": "openai_compat", "model": ov["fallback_model"]}
            else:
                conf["fallback"] = None
    model_env = os.environ.get(f"GIGBID_MODEL_{node.upper()}") or os.environ.get("GIGBID_MODEL")
    if model_env and conf.get("provider") != "heuristic":
        conf["model"] = model_env
    return conf


def is_heuristic(node: str = "writer") -> bool:
    return node_config(node).get("provider") in (None, "heuristic")


def _build(conf: dict):
    prov = conf.get("provider")
    timeout = conf.get("timeout_s", 60)
    if prov == "ollama":
        from langchain_ollama import ChatOllama

        base = os.environ.get(conf.get("base_url_env") or "OLLAMA_BASE_URL") or conf.get(
            "base_url_default", "http://localhost:11434")
        return ChatOllama(model=conf["model"], base_url=base, temperature=conf.get("temperature", 0.2),
                          num_predict=conf.get("max_tokens", 800), client_kwargs={"timeout": timeout})
    if prov == "openai_compat":
        from langchain_openai import ChatOpenAI

        base = os.environ.get(conf.get("base_url_env") or "") or conf.get("base_url_default")
        key = os.environ.get(conf.get("api_key_env") or "") or "missing-key"
        kw = {"reasoning_effort": conf["reasoning_effort"]} if conf.get("reasoning_effort") else {}
        return ChatOpenAI(model=conf["model"], base_url=base, api_key=key,
                          temperature=conf.get("temperature", 0.2), max_tokens=conf.get("max_tokens", 800),
                          timeout=timeout, max_retries=int(conf.get("max_retries", 1)), **kw)
    return None


_cache: dict[str, Any] = {}


def get_llm(node: str):
    """Chat model for a node, with the configured fallback model attached (or None for heuristic)."""
    conf = node_config(node)
    key = json.dumps(conf, sort_keys=True, default=str)
    if key in _cache:
        return _cache[key]
    primary = _build(conf)
    if primary is not None and conf.get("fallback"):
        fb_conf = {**conf, **conf["fallback"]}
        fb_conf.pop("fallback", None)
        fb = _build(fb_conf)
        if fb is not None:
            primary = primary.with_fallbacks([fb])
    _cache[key] = primary
    return primary


def _price(model: str, tin: int, tout: int) -> float:
    table = cfg("pricing_usd_per_mtok", default={}) or {}
    p = table.get(model) or table.get("default_local") or [0.0, 0.0]
    return (tin * p[0] + tout * p[1]) / 1_000_000


def _record(node: str, res: LLMResult) -> None:
    with _lock:
        t = USAGE_TOTALS.setdefault(node, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                                           "latency_ms": 0.0, "failures": 0})
        t["calls"] += 1
        t["tokens_in"] += res.tokens_in
        t["tokens_out"] += res.tokens_out
        t["cost_usd"] += res.cost_usd
        t["latency_ms"] += res.latency_ms
        if not res.ok:
            t["failures"] += 1


def reset_usage() -> None:
    with _lock:
        USAGE_TOTALS.clear()


_last_call: dict[str, float] = {}


def _invoke_polite(llm, msgs):
    """Respect hosted free-tier limits: minimum spacing between calls and backoff on HTTP 429."""
    prov = provider_name()
    gap = float((cfg("rate_limit", "min_interval_s", default={}) or {}).get(prov, 0) or 0)
    retries = int(cfg("rate_limit", "max_429_retries", default=3))
    backoff = float(cfg("rate_limit", "backoff_s", default=3.0))
    for attempt in range(retries + 1):
        if gap:
            with _lock:
                wait = _last_call.get(prov, 0) + gap - time.time()
                _last_call[prov] = max(time.time(), _last_call.get(prov, 0) + gap)
            if wait > 0:
                time.sleep(wait)
        try:
            return llm.invoke(msgs)
        except Exception as exc:
            msg = f"{type(exc).__name__} {exc}".lower()
            if attempt < retries and ("429" in msg or "rate limit" in msg or "ratelimit" in msg):
                time.sleep(backoff * (2 ** attempt))
                continue
            raise


def load_env_file(path: str) -> list[str]:
    """Load KEY=VALUE lines into os.environ (values are never printed). Returns the keys loaded."""
    keys = []
    if not path or not os.path.exists(path):
        return keys
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().removeprefix("export ").strip()
        os.environ.setdefault(k, v.strip().strip('"').strip("'"))
        keys.append(k)
    return keys


def extract_json(text: str) -> Any:
    """Parse the first JSON object/array in a model response."""
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"```(?:json)?", "", text)
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


def call_llm(node: str, prompt: str, variables: dict | None = None, *, json_mode: bool = False,
             system_prompt: str | None = "system") -> LLMResult:
    """Render prompt `agent/prompts/<prompt>.md`, call the node's model, account tokens and cost."""
    conf = node_config(node)
    if conf.get("provider") in (None, "heuristic"):
        return LLMResult(ok=False, error="heuristic")
    llm = get_llm(node)
    if llm is None:
        return LLMResult(ok=False, error="no-llm")
    from langchain_core.messages import HumanMessage, SystemMessage

    body, version = render_prompt(prompt, variables or {})
    msgs = []
    if system_prompt:
        sys_text, _ = render_prompt(system_prompt, {})
        msgs.append(SystemMessage(sys_text))
    msgs.append(HumanMessage(body))
    t0 = time.perf_counter()
    try:
        out = _invoke_polite(llm, msgs)
    except Exception as exc:  # network/model failure → deterministic path
        res = LLMResult(ok=False, error=f"{type(exc).__name__}: {exc}"[:300], model=conf.get("model", "?"),
                        latency_ms=(time.perf_counter() - t0) * 1000, prompt_version=version)
        _record(node, res)
        return res
    latency = (time.perf_counter() - t0) * 1000
    um = getattr(out, "usage_metadata", None) or {}
    tin = int(um.get("input_tokens") or 0)
    tout = int(um.get("output_tokens") or 0)
    model_used = (getattr(out, "response_metadata", {}) or {}).get("model_name") or (
        getattr(out, "response_metadata", {}) or {}).get("model") or conf.get("model")
    if not tin and not tout:  # rough estimate when the server does not report usage
        tin = sum(len(m.content) for m in msgs) // 4
        tout = len(out.content or "") // 4
    text = out.content if isinstance(out.content, str) else str(out.content)
    res = LLMResult(ok=True, text=text, model=str(model_used), tokens_in=tin, tokens_out=tout,
                    cost_usd=_price(str(conf.get("model")), tin, tout), latency_ms=latency,
                    fallback_used=bool(model_used and conf.get("model") and conf["model"] not in str(model_used)),
                    prompt_version=version)
    if json_mode:
        res.data = extract_json(text)
        if res.data is None:
            res.ok = False
            res.error = "unparseable-json"
    _record(node, res)
    return res
