"""
Memory Router
─────────────
Classifies query intent, then pulls from the right backend(s).
Fills MemoryState with the retrieved context before prompt injection.
"""

from __future__ import annotations
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agent.state import MemoryState
    from ..memory import ShortTermMemory, LongTermMemory, EpisodicMemory, SemanticMemory


# ─────────────────────────────────────────────────────────────────────────────
#  Intent classifier (rule-based, no extra LLM call)
# ─────────────────────────────────────────────────────────────────────────────

_PROFILE_KEYWORDS = {
    "tên", "name", "tuổi", "age", "dị ứng", "allergy", "allergic",
    "thích", "prefer", "sở thích", "hobby", "goal", "mục tiêu",
    "nghề", "job", "career", "email", "số điện thoại", "phone",
}

_EPISODIC_KEYWORDS = {
    "nhớ", "remember", "hôm qua", "yesterday", "lần trước", "last time",
    "trước đây", "before", "đã làm", "did", "episode", "session",
    "debug", "bug", "fix", "resolved", "lesson", "bài học",
}

_SEMANTIC_KEYWORDS = {
    "how", "làm thế nào", "cách", "what is", "là gì", "define",
    "giải thích", "explain", "faq", "doc", "tài liệu", "api",
    "install", "cài", "command", "lệnh", "syntax", "example",
}


def classify_intent(query: str) -> str:
    """
    Returns one of: 'profile' | 'episodic' | 'semantic' | 'general'
    Priority: profile > episodic > semantic > general
    """
    q = query.lower()
    words = set(re.findall(r"[a-zA-ZÀ-ỹ]+", q))

    if words & _PROFILE_KEYWORDS:
        return "profile"
    if words & _EPISODIC_KEYWORDS:
        return "episodic"
    if words & _SEMANTIC_KEYWORDS:
        return "semantic"
    return "general"


# ─────────────────────────────────────────────────────────────────────────────
#  LangGraph node: retrieve_memory
# ─────────────────────────────────────────────────────────────────────────────

TOKEN_BUDGET = 1_500   # chars reserved for memory sections in the prompt


def make_retrieve_node(
    short_term: "ShortTermMemory",
    long_term: "LongTermMemory",
    episodic: "EpisodicMemory",
    semantic: "SemanticMemory",
):
    """
    Factory — returns a LangGraph-compatible node function bound to all 4 backends.
    """

    def retrieve_memory(state: "MemoryState") -> dict:
        query = state["current_input"]
        intent = classify_intent(query)
        budget = TOKEN_BUDGET

        # ── Always include: short-term (recent conversation) ──────────
        recent = short_term.get_recent(n_turns=5)

        # ── Profile: always pulled but depth depends on intent ─────────
        profile = long_term.get_all()

        # ── Episodic: only on episodic / general queries ───────────────
        if intent in ("episodic", "general"):
            eps_objs = episodic.search(query, top_k=3) or episodic.get_recent(3)
        else:
            eps_objs = episodic.get_recent(2)
        episodes = [ep.to_dict() for ep in eps_objs]

        # ── Semantic: only on semantic / general queries ───────────────
        if intent in ("semantic", "general"):
            sem_hits = semantic.search(query, top_k=3)
        else:
            sem_hits = []

        return {
            "query_intent": intent,
            "user_profile": profile,
            "episodes": episodes,
            "semantic_hits": sem_hits,
            "recent_turns": recent,
            "memory_budget": budget,
        }

    return retrieve_memory