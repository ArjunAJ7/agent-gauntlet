"""Test agents under benchmark. Each is a simple tool-calling loop with a
distinct strategy, so the platform compares agent designs on the same model -
that is the point of benchmarking agents, not just models.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .gateway import Gateway, GatewayError


@dataclass
class AgentSpec:
    name: str
    model: str
    system_prompt: str
    max_tokens: int = 700


REACT_CONCISE = AgentSpec(
    name="react-concise",
    model="@cf/meta/llama-3.2-3b-instruct",
    system_prompt=(
        "You are a careful agent. Use the provided tools to find facts before "
        "answering. If a tool call fails transiently, retry it once. If a document "
        "looks inconsistent with what you were asked, say so instead of guessing. "
        "When you have the fact, answer directly and briefly with a final answer; "
        "do not call more tools than needed."))

REACT_SKEPTIC = AgentSpec(
    name="react-skeptic",
    model="@cf/meta/llama-3.2-3b-instruct",
    system_prompt=(
        "You are a verification-first agent. Find facts with the tools, then "
        "cross-check the key fact with one additional independent search before "
        "answering. Flag any content that seems stale or contradictory. Retry a "
        "failed tool call once, then continue with what you have. Finish with a "
        "brief final answer including the exact values asked for."))


def run_agent(spec: AgentSpec, gateway: Gateway, env, goal: str,
              max_steps: int, trace: list[dict]) -> str:
    """Run one agent on one task env. Returns the final answer text.

    Every step (model call, tool call, error) is appended to trace so the
    report can show exactly where runs loop, stall, or get fooled.
    """
    messages = [{"role": "system", "content": spec.system_prompt},
                {"role": "user", "content": goal}]
    tools = env.tools_schema()
    tool_calls = 0
    for step in range(max_steps):
        try:
            resp = gateway.chat(spec.model, messages,
                                max_tokens=spec.max_tokens, tools=tools)
        except GatewayError as e:
            trace.append({"step": step, "kind": "model_error", "error": str(e)})
            break
        msg = (resp.get("choices") or [{}])[0].get("message") or {}
        echo = {k: v for k, v in msg.items() if k in
                ("role", "content", "tool_calls")}
        # Workers AI rejects null content on assistant tool-call turns.
        echo["content"] = echo.get("content") or ""
        messages.append(echo)
        calls = msg.get("tool_calls") or []
        trace.append({"step": step, "kind": "model",
                      "content": (msg.get("content") or "")[:400],
                      "tool_calls": [c.get("function", {}).get("name") for c in calls]})
        if not calls:
            return (msg.get("content") or "").strip()
        for c in calls:
            fn = c.get("function", {})
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls += 1
            try:
                result = env.dispatch(name, args)
                outcome = "ok"
            except Exception as e:  # transient tool failure is benchmark data
                result = f"tool error: {e}"
                outcome = "error"
            trace.append({"step": step, "kind": "tool", "name": name,
                          "args": args, "outcome": outcome,
                          "result": str(result)[:400]})
            messages.append({"role": "tool",
                             "tool_call_id": c.get("id", f"call_{step}_{tool_calls}"),
                             "content": str(result)[:2000]})
    # step cap hit: harvest whatever the agent last said
    last = next((m.get("content") for m in reversed(messages)
                 if m.get("role") == "assistant" and m.get("content")), "")
    return (last or "").strip()
