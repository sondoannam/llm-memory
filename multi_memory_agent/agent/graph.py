"""
LangGraph Graph
───────────────
Wires all nodes into a directed graph:

  [START] → retrieve_memory → call_llm → save_memory → [END]

Each node is a pure function: (state) → partial state update dict.
"""

from __future__ import annotations
import json
import os
import re
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from ..agent.state import MemoryState
from ..agent.router import make_retrieve_node
from ..agent.prompt import build_system_prompt, build_messages_for_api
from ..memory import ShortTermMemory, LongTermMemory, EpisodicMemory, SemanticMemory


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: LLM call
# ─────────────────────────────────────────────────────────────────────────────

def _get_llm(max_tokens: int = 1024):
    provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
    if provider == "openai":
        return ChatOpenAI(
            model="gpt-4o",
            max_tokens=max_tokens,
            temperature=0.0
        )
    else:
        # Default to Ollama local
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        base_url = os.environ.get("OLLAMA_API_BASE", "http://localhost:11434")
        return ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.0
        )

def _call_llm(system: str, messages: list[dict], max_tokens: int = 1024) -> str:
    langchain_messages = [SystemMessage(content=system)]
    for m in messages:
        if m["role"] == "user":
            langchain_messages.append(HumanMessage(content=m["content"]))
            
    llm = _get_llm(max_tokens=max_tokens)
    try:
        resp = llm.invoke(langchain_messages)
        return resp.content
    except Exception as e:
        return f"[Error invoking LLM {e}]"


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: extract facts from conversation turn (lightweight)
# ─────────────────────────────────────────────────────────────────────────────

FACT_EXTRACT_SYSTEM = """Extract user facts from the message as a JSON dict.
Keys: name, age, allergy, preference, goal, job, location, or any other user-stated attribute.
Only include facts explicitly stated. Return {} if none.
Return ONLY valid JSON, no explanation."""


def _extract_facts(user_message: str) -> dict:
    try:
        text = _call_llm(
            system=FACT_EXTRACT_SYSTEM,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=200,
        )
        text = re.sub(r"```json|```", "", text).strip()
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1:
            clean_json = text[start_idx:end_idx+1]
            return json.loads(clean_json)
        return {}
    except Exception:
        return {}


def _should_save_episode(assistant_response: str, user_input: str) -> bool:
    """Heuristic: save episode when the assistant resolves something meaningful."""
    completion_signals = [
        "xong", "hoàn tất", "done", "completed", "resolved", "fixed",
        "thành công", "success", "saved", "đã lưu", "understood",
        "got it", "tôi hiểu", "đã ghi nhận"
    ]
    combined = (assistant_response + user_input).lower()
    return any(s in combined for s in completion_signals)


# ─────────────────────────────────────────────────────────────────────────────
#  Graph factory
# ─────────────────────────────────────────────────────────────────────────────

def build_graph(
    short_term: ShortTermMemory,
    long_term: LongTermMemory,
    episodic: EpisodicMemory,
    semantic: SemanticMemory,
):
    """
    Returns a compiled LangGraph for the multi-memory agent.
    """

    # ── Node 1: retrieve_memory ───────────────────────────────────────
    retrieve_memory = make_retrieve_node(short_term, long_term, episodic, semantic)

    # ── Node 2: call_llm ──────────────────────────────────────────────
    def call_llm(state: MemoryState) -> dict:
        system_prompt = build_system_prompt(
            user_profile=state["user_profile"],
            episodes=state["episodes"],
            semantic_hits=state["semantic_hits"],
            recent_turns=state["recent_turns"],
            memory_budget=state["memory_budget"],
        )
        _, messages = build_messages_for_api(system_prompt, state["current_input"])

        response = _call_llm(system=system_prompt, messages=messages)

        # Extract facts for persistence
        facts = _extract_facts(state["current_input"])

        # Decide whether to record an episode
        episode = None
        if _should_save_episode(response, state["current_input"]):
            episode = {
                "summary": f"User: {state['current_input'][:80]} | Agent: {response[:80]}",
                "outcome": "success",
                "tags": [state.get("query_intent", "general")],
                "session_id": state.get("session_id", ""),
            }

        return {
            "response": response,
            "extracted_facts": facts,
            "episode_to_save": episode,
        }

    # ── Node 3: save_memory ───────────────────────────────────────────
    def save_memory(state: MemoryState) -> dict:
        # Persist to short-term (both user input and assistant response)
        short_term.add("user", state["current_input"])
        short_term.add("assistant", state["response"])

        # Persist facts to long-term profile (conflict resolution built in)
        if state.get("extracted_facts"):
            long_term.set_many(state["extracted_facts"])

        # Persist episode if flagged
        ep_dict = state.get("episode_to_save")
        if ep_dict:
            episodic.save_episode(
                summary=ep_dict["summary"],
                outcome=ep_dict["outcome"],
                tags=ep_dict.get("tags", []),
                session_id=ep_dict.get("session_id", ""),
            )

        return {}   # no state change needed

    # ── Build the graph ───────────────────────────────────────────────
    builder = StateGraph(MemoryState)
    builder.add_node("retrieve_memory", retrieve_memory)
    builder.add_node("call_llm", call_llm)
    builder.add_node("save_memory", save_memory)

    builder.add_edge(START, "retrieve_memory")
    builder.add_edge("retrieve_memory", "call_llm")
    builder.add_edge("call_llm", "save_memory")
    builder.add_edge("save_memory", END)

    return builder.compile()