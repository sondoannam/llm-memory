"""
LangGraph State Definition
Everything the graph nodes read/write lives here.
"""

from __future__ import annotations
from typing import Annotated, Any, List, TypedDict
import operator


class MemoryState(TypedDict):
    # ── Conversation ──────────────────────────────────────────────────
    messages: List[dict]               # full chat history [{role, content}]
    current_input: str                 # latest user turn (convenience)
    session_id: str

    # ── Retrieved memory sections ─────────────────────────────────────
    user_profile: dict                 # from LongTermMemory
    episodes: List[dict]              # from EpisodicMemory
    semantic_hits: List[str]          # from SemanticMemory
    recent_turns: List[dict]          # from ShortTermMemory (trimmed)

    # ── Routing metadata ──────────────────────────────────────────────
    query_intent: str                  # "profile" | "episodic" | "semantic" | "general"
    memory_budget: int                 # remaining token budget for memory section

    # ── Agent response ────────────────────────────────────────────────
    response: str

    # ── Facts to persist ─────────────────────────────────────────────
    extracted_facts: dict              # key-value facts to write to LongTermMemory
    episode_to_save: dict | None      # episode dict to append to EpisodicMemory