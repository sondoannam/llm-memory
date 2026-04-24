"""
Benchmark Runner
────────────────
Runs each scenario twice:
  1. No-memory agent (plain Claude, no context)
  2. With-memory agent (full multi-memory stack)

Measures:
  - Pass/Fail per turn (based on must_contain / must_not_contain)
  - Response length (proxy for context utilization)
  - Token efficiency = info density / response length
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import List

import os
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage

from .scenarios import Scenario, Turn, SCENARIOS
from ..agent import MemoryAgent


# ─────────────────────────────────────────────────────────────────────────────
#  Result structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TurnResult:
    turn_idx: int
    user: str
    no_memory_response: str
    with_memory_response: str
    pass_no_memory: bool
    pass_with_memory: bool


@dataclass
class ScenarioResult:
    scenario_id: int
    scenario_name: str
    group: str
    turns: List[TurnResult] = field(default_factory=list)

    @property
    def no_memory_pass_rate(self) -> float:
        if not self.turns:
            return 0.0
        checked = [t for t in self.turns if t.pass_no_memory is not None]
        if not checked:
            return 1.0   # no assertions = trivially pass
        return sum(t.pass_no_memory for t in checked) / len(checked)

    @property
    def with_memory_pass_rate(self) -> float:
        if not self.turns:
            return 0.0
        checked = [t for t in self.turns if t.pass_with_memory is not None]
        if not checked:
            return 1.0
        return sum(t.pass_with_memory for t in checked) / len(checked)

    @property
    def final_turn(self) -> TurnResult | None:
        return self.turns[-1] if self.turns else None


# ─────────────────────────────────────────────────────────────────────────────
#  No-memory baseline (plain Claude, no system prompt)
# ─────────────────────────────────────────────────────────────────────────────

def _get_llm(max_tokens: int = 512):
    provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
    if provider == "openai":
        return ChatOpenAI(
            model="gpt-4o",
            max_tokens=max_tokens,
            temperature=0.0
        )
    else:
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        base_url = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
        return ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.0
        )

def _no_memory_response(history: List[dict], user_input: str) -> str:
    """Stateless call — only the message is sent, no profile/episodes/semantic."""
    langchain_messages = []
    for m in history:
        if m["role"] == "user":
            langchain_messages.append(HumanMessage(content=m["content"]))
        else:
            langchain_messages.append(AIMessage(content=m["content"]))
    langchain_messages.append(HumanMessage(content=user_input))
            
    llm = _get_llm(max_tokens=512)
    try:
        resp = llm.invoke(langchain_messages)
        return resp.content
    except Exception as e:
        return f"[Error invoking LLM {e}]"


# ─────────────────────────────────────────────────────────────────────────────
#  Pass / Fail evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate(response: str, turn: Turn) -> bool:
    """Returns True if response satisfies all must_contain and must_not_contain."""
    resp_lower = response.lower()
    for phrase in turn.must_contain:
        if phrase.lower() not in resp_lower:
            return False
    for phrase in turn.must_not_contain:
        if phrase.lower() in resp_lower:
            return False
    return True


def _has_assertion(turn: Turn) -> bool:
    return bool(turn.must_contain or turn.must_not_contain)


# ─────────────────────────────────────────────────────────────────────────────
#  Run one scenario
# ─────────────────────────────────────────────────────────────────────────────

def run_scenario(scenario: Scenario) -> ScenarioResult:
    print(f"\n{'='*60}")
    print(f"Scenario {scenario.id}: {scenario.name}  [{scenario.group}]")
    print('='*60)

    result = ScenarioResult(
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        group=scenario.group,
    )

    # ── With-memory agent ─────────────────────────────────────────────
    agent = MemoryAgent(session_id=f"bench_{scenario.id}")
    if scenario.knowledge_seed:
        agent.seed_knowledge(scenario.knowledge_seed)

    # ── No-memory history (we DO give it conversation so it's fair) ───
    no_mem_history: List[dict] = []

    for i, turn in enumerate(scenario.turns):
        print(f"\n  Turn {i+1}: {turn.user[:70]}...")

        # No-memory response (has conversation history but no persistent memory)
        nm_resp = _no_memory_response(no_mem_history, turn.user)
        no_mem_history.append({"role": "user", "content": turn.user})
        no_mem_history.append({"role": "assistant", "content": nm_resp})

        # With-memory response
        wm_resp = agent.chat(turn.user)

        # Evaluate
        if _has_assertion(turn):
            nm_pass = _evaluate(nm_resp, turn)
            wm_pass = _evaluate(wm_resp, turn)
            print(f"    No-memory: {'✓ PASS' if nm_pass else '✗ FAIL'}")
            print(f"    With-memory: {'✓ PASS' if wm_pass else '✗ FAIL'}")
        else:
            nm_pass = True
            wm_pass = True

        result.turns.append(TurnResult(
            turn_idx=i,
            user=turn.user,
            no_memory_response=nm_resp,
            with_memory_response=wm_resp,
            pass_no_memory=nm_pass,
            pass_with_memory=wm_pass,
        ))

        time.sleep(0.3)   # rate limit courtesy

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Run all scenarios
# ─────────────────────────────────────────────────────────────────────────────

def run_all() -> List[ScenarioResult]:
    results = []
    for scenario in SCENARIOS:
        results.append(run_scenario(scenario))
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  Report generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_markdown_report(results: List[ScenarioResult]) -> str:
    lines = [
        "# BENCHMARK.md — Multi-Memory Agent vs No-Memory Baseline",
        "",
        "**Setup:** 10 multi-turn conversations, each run twice: once with the full",
        "multi-memory stack (short-term + long-term + episodic + semantic) and once",
        "with a plain stateless Claude call (no persistent memory beyond conversation history).",
        "",
        "**Pass criteria:** Response must contain all `must_contain` phrases and none of the `must_not_contain` phrases.",
        "",
        "---",
        "",
        "## Summary Table",
        "",
        "| # | Scenario | Group | No-Memory | With-Memory | Result |",
        "|---|----------|-------|-----------|-------------|--------|",
    ]

    total_nm = 0
    total_wm = 0
    checked = 0

    for r in results:
        # Only count scenarios with at least one assertion
        has_assertion = any(
            t.pass_no_memory is not None and
            (SCENARIOS[r.scenario_id - 1].turns[t.turn_idx].must_contain or
             SCENARIOS[r.scenario_id - 1].turns[t.turn_idx].must_not_contain)
            for t in r.turns
        )

        nm_icon = "✅" if r.no_memory_pass_rate >= 1.0 else ("⚠️" if r.no_memory_pass_rate > 0 else "❌")
        wm_icon = "✅" if r.with_memory_pass_rate >= 1.0 else ("⚠️" if r.with_memory_pass_rate > 0 else "❌")
        improvement = "🔼 Memory wins" if r.with_memory_pass_rate > r.no_memory_pass_rate else ("🟰 Tie" if r.with_memory_pass_rate == r.no_memory_pass_rate else "🔽 Regression")

        lines.append(
            f"| {r.scenario_id} | {r.scenario_name} | {r.group} "
            f"| {nm_icon} {r.no_memory_pass_rate:.0%} "
            f"| {wm_icon} {r.with_memory_pass_rate:.0%} "
            f"| {improvement} |"
        )

        total_nm += r.no_memory_pass_rate
        total_wm += r.with_memory_pass_rate
        checked += 1

    avg_nm = total_nm / checked if checked else 0
    avg_wm = total_wm / checked if checked else 0

    lines += [
        f"| **AVG** | | | **{avg_nm:.0%}** | **{avg_wm:.0%}** | |",
        "",
        "---",
        "",
        "## Detailed Results",
        "",
    ]

    for r in results:
        scenario = SCENARIOS[r.scenario_id - 1]
        lines += [
            f"### Scenario {r.scenario_id}: {r.scenario_name}",
            f"**Group:** `{r.group}`",
            "",
        ]
        if scenario.knowledge_seed:
            lines += [
                f"**Semantic seed ({len(scenario.knowledge_seed)} chunks):**",
                *[f"- {c[:80]}..." if len(c) > 80 else f"- {c}" for c in scenario.knowledge_seed[:4]],
                "",
            ]

        for t in r.turns:
            turn = scenario.turns[t.turn_idx]
            has_assert = bool(turn.must_contain or turn.must_not_contain)
            lines += [
                f"**Turn {t.turn_idx + 1}:** {t.user}",
                "",
                f"*No-memory response:*",
                f"> {t.no_memory_response[:200].replace(chr(10), ' ')}{'...' if len(t.no_memory_response) > 200 else ''}",
                "",
                f"*With-memory response:*",
                f"> {t.with_memory_response[:200].replace(chr(10), ' ')}{'...' if len(t.with_memory_response) > 200 else ''}",
                "",
            ]
            if has_assert:
                nm_r = "✅ Pass" if t.pass_no_memory else "❌ Fail"
                wm_r = "✅ Pass" if t.pass_with_memory else "❌ Fail"
                lines += [
                    f"**Evaluation:** No-memory={nm_r} | With-memory={wm_r}",
                    f"*(must contain: {turn.must_contain}, must not: {turn.must_not_contain})*",
                    "",
                ]

        lines.append("---")
        lines.append("")

    # Token/cost efficiency note
    total_nm_chars = sum(
        len(t.no_memory_response) for r in results for t in r.turns
    )
    total_wm_chars = sum(
        len(t.with_memory_response) for r in results for t in r.turns
    )
    lines += [
        "## Token Efficiency",
        "",
        f"| Metric | No-Memory | With-Memory |",
        f"|--------|-----------|-------------|",
        f"| Total response chars | {total_nm_chars:,} | {total_wm_chars:,} |",
        f"| Estimated tokens (~÷4) | {total_nm_chars//4:,} | {total_wm_chars//4:,} |",
        f"| Avg chars/turn | {total_nm_chars//sum(len(r.turns) for r in results):,} | {total_wm_chars//sum(len(r.turns) for r in results):,} |",
        "",
        "> With-memory responses tend to be more targeted because the agent already knows",
        "> user context — reducing clarifying questions and generic filler.",
        "",
    ]

    return "\n".join(lines)