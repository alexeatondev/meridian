"""Claude Agent SDK backend.

Each judgment runs as one agent session: the agent's AGENT.md and skills are the system prompt, the
only tools it can reach are the read-only Meridian tools passed for that step, and the answer must
match a JSON schema. Cost is bounded three ways:

- ``MERIDIAN_RUN_BUDGET_USD``   (default 3.00): total spend for one pipeline run. When it is used up,
  remaining judgments fall back to the deterministic policy and the ledger records why.
- ``MERIDIAN_AGENT_BUDGET_USD`` (default 0.25): cap for a single agent session.
- ``MERIDIAN_AGENT_MAX_TURNS``  (default 8): cap on agent turns in one session.

Three failed sessions in a row (bad key, outage) switch the backend off for the rest of the run.

Other settings: ``MERIDIAN_AGENT_EFFORT`` (default ``low``; empty string leaves the model default),
``MERIDIAN_AGENT_TIMEOUT_S`` (default 240), ``MERIDIAN_MODEL`` and per-agent ``MERIDIAN_MODEL_<SLUG>``.

No built-in tools (shell, file access, web) are available to the agents, and no project or user
settings are loaded, so an agent cannot read the repository, write files or reach the network.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from .runtime import AgentSpec, LLMBackend, _new_usage

SERVER = "meridian"
# Conservative fallback rates (USD per million tokens) used only if the SDK reports no cost for a session.
_FALLBACK_IN, _FALLBACK_OUT = 5.0, 25.0


def _sdk():
    import claude_agent_sdk  # type: ignore
    return claude_agent_sdk


def _f(env: str, default: float) -> float:
    try:
        return float(os.getenv(env, "") or default)
    except ValueError:
        return default


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(1) as ex:           # called from inside a running loop: use a private one
        return ex.submit(asyncio.run, coro).result()


class AgentSDKBackend(LLMBackend):
    """Runs each judgment as a Claude Agent SDK session with read-only tools and spend caps."""

    name = "sdk"
    path_name = "agent"

    def __init__(self):
        self.model = os.getenv("MERIDIAN_MODEL", "claude-opus-5-5")
        self.enabled = bool(os.getenv("ANTHROPIC_API_KEY")) and os.getenv("MERIDIAN_LLM", "on") != "off"
        self.usage = {**_new_usage(), "backend": "claude-agent-sdk", "cost_usd": 0.0, "tool_calls": 0, "turns": 0,
                      "budget_usd": _f("MERIDIAN_RUN_BUDGET_USD", 3.0), "skipped_over_budget": 0}
        self.last_trace = None
        self.agent_budget = _f("MERIDIAN_AGENT_BUDGET_USD", 0.25)
        self.max_turns = int(_f("MERIDIAN_AGENT_MAX_TURNS", 8))
        self.timeout_s = _f("MERIDIAN_AGENT_TIMEOUT_S", 240)
        self.effort = os.getenv("MERIDIAN_AGENT_EFFORT", "low") or None
        self._cwd = None
        self._streak = 0             # consecutive failed sessions; three in a row switches the backend off for the run
        if self.enabled:
            try:
                self.runtime = "claude-agent-sdk " + getattr(_sdk(), "__version__", "?")
                self._cwd = tempfile.mkdtemp(prefix="meridian-agent-")   # empty dir: nothing for an agent to find
            except ImportError:
                self.enabled = False

    # ------------------------------------------------------------------------------------------ budget
    @property
    def remaining(self) -> float:
        return self.usage["budget_usd"] - self.usage["cost_usd"]

    # ------------------------------------------------------------------------------------------ judge
    def judge(self, spec: AgentSpec, task: str, context: dict, schema_hint: str,
              tools: list | None = None, schema: dict | None = None) -> dict | None:
        self.last_trace = None
        if not self.enabled:
            return None
        if self.remaining < 0.01:
            self.usage["skipped_over_budget"] += 1
            self.last_trace = {"runtime": self.runtime, "skipped": "run budget used up",
                               "budget_usd": self.usage["budget_usd"], "spent_usd": round(self.usage["cost_usd"], 4)}
            return None
        self.usage["calls"] += 1
        trace = {"runtime": self.runtime, "model": self.model_for(spec), "tools_offered": [t.name for t in tools or []],
                 "tool_calls": [], "turns": 0, "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
        out = None
        try:
            out = _run_sync(asyncio.wait_for(self._session(spec, task, context, schema_hint, tools or [], schema, trace),
                                             timeout=self.timeout_s))
        except Exception as e:  # CLI missing, API error, timeout, budget or turn cap raised by the SDK
            trace["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        self._account(trace)
        if not isinstance(out, dict):
            out = None
            self.usage["failures"] += 1
            self.usage["errors"].append(f"{spec.slug}: {trace.get('error') or trace.get('stop') or 'no usable output'}")
            self._streak += 1
            if self._streak >= 3:    # e.g. bad key or outage: stop paying start-up time for sessions that cannot work
                self.enabled = False
                self.usage["disabled"] = "three agent sessions failed in a row; the rest of the run used the deterministic policy"
        else:
            self._streak = 0
        self.last_trace = trace
        return out

    def _account(self, trace: dict) -> None:
        if not trace["cost_usd"] and (trace["input_tokens"] or trace["output_tokens"]):
            trace["cost_usd"] = (trace["input_tokens"] * _FALLBACK_IN + trace["output_tokens"] * _FALLBACK_OUT) / 1e6
            trace["cost_estimated"] = True
        trace["cost_usd"] = round(float(trace["cost_usd"]), 6)
        u = self.usage
        u["cost_usd"] = round(u["cost_usd"] + trace["cost_usd"], 6)
        u["input_tokens"] += trace["input_tokens"]
        u["output_tokens"] += trace["output_tokens"]
        u["tool_calls"] += len(trace["tool_calls"])
        u["turns"] += trace["turns"]

    # ------------------------------------------------------------------------------------------ session
    def _options(self, sdk, spec: AgentSpec, tools: list, schema: dict | None, trace: dict):
        servers, allowed = {}, []
        if tools:
            servers = {SERVER: sdk.create_sdk_mcp_server(name=SERVER, version="1.0.0",
                                                         tools=[self._wrap(sdk, t, trace) for t in tools])}
            allowed = [f"mcp__{SERVER}__{t.name}" for t in tools]
        kw = dict(system_prompt=spec.system_prompt, tools=[], mcp_servers=servers, allowed_tools=allowed,
                  setting_sources=[], model=self.model_for(spec), max_turns=self.max_turns,
                  max_budget_usd=round(max(0.01, min(self.agent_budget, self.remaining)), 4), cwd=self._cwd)
        if schema:
            kw["output_format"] = {"type": "json_schema", "schema": schema}
        if self.effort:
            kw["effort"] = self.effort
        return sdk.ClaudeAgentOptions(**kw)

    @staticmethod
    def _wrap(sdk, t, trace: dict):
        async def handler(args):
            call = {"tool": t.name, "input": args}
            trace["tool_calls"].append(call)
            try:
                text = json.dumps(t.fn(args or {}), default=str)
                call["result_chars"] = len(text)
                return {"content": [{"type": "text", "text": text[:20000]}]}
            except Exception as e:  # bad arguments from the model: tell it, don't crash the run
                call["error"] = f"{type(e).__name__}: {str(e)[:200]}"
                return {"content": [{"type": "text", "text": "Error: " + call["error"]}], "is_error": True}
        return sdk.tool(t.name, t.description, t.schema)(handler)

    async def _session(self, spec, task, context, schema_hint, tools, schema, trace) -> dict | None:
        sdk = _sdk()
        hint = ""
        if tools:
            hint = ("\n\nTOOLS: " + "; ".join(f"{t.name} ({t.description})" for t in tools) + ". They are read-only and "
                    "return data computed by code. Call a tool only if its result could change your answer, and make "
                    "at most three tool calls. Never do arithmetic yourself when a tool can compute it.")
        prompt = (f"TASK:\n{task}\n\nOUTPUT SCHEMA:\n{schema_hint}{hint}\n\n"
                  f"CONTEXT (data):\n{json.dumps(context, default=str)[:60000]}")
        out, text = None, ""
        try:
            async for m in sdk.query(prompt=prompt, options=self._options(sdk, spec, tools, schema, trace)):
                if isinstance(m, sdk.ResultMessage):
                    trace["turns"] = int(m.num_turns or 0)
                    trace["stop"] = "error" if getattr(m, "is_error", False) else m.subtype
                    trace["session_id"] = m.session_id
                    trace["cost_usd"] = float(m.total_cost_usd or 0.0)
                    u = m.usage or {}
                    trace["input_tokens"] = int(sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                                             "cache_read_input_tokens")))
                    trace["output_tokens"] = int(u.get("output_tokens") or 0)
                    out, text = m.structured_output, m.result or ""
        except Exception as e:  # the SDK raises after an error result (budget or turn cap); keep what was captured
            trace["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        if not isinstance(out, dict) and text and "{" in text:
            try:
                out = json.loads(text[text.find("{"): text.rfind("}") + 1])
            except ValueError:
                out = None
        return out if isinstance(out, dict) else None
