"""
Prompt Builder
──────────────
Assembles the system prompt by injecting all 4 memory sections.
Respects a token budget — trims sections in priority order.
"""

from __future__ import annotations
from typing import List

# Section priority for eviction (lowest priority trimmed first)
# 4 = highest (keep last), 1 = lowest (trim first)
SECTION_PRIORITY = {
    "semantic": 1,
    "episodic": 2,
    "profile": 3,
    "recent": 4,
}

SYSTEM_TEMPLATE = """You are a helpful AI assistant with a multi-layer memory system.

## User Profile
{profile_section}

## Relevant Past Episodes
{episodic_section}

## Knowledge / Semantic Context
{semantic_section}

## Recent Conversation
{recent_section}

---
Use the above context to give accurate, personalised responses.
If user corrects a fact, acknowledge the update. Never contradict confirmed user facts.
"""


def _trim_to_budget(text: str, budget: int) -> str:
    """Trim a string to fit within a rough char budget."""
    if len(text) <= budget:
        return text
    return text[:budget - 3] + "..."


def build_system_prompt(
    user_profile: dict,
    episodes: List[dict],
    semantic_hits: List[str],
    recent_turns: List[dict],
    memory_budget: int = 1_500,
) -> str:
    """
    Build the full system prompt. Sections are trimmed if total exceeds budget.
    """

    # ── Render each section ───────────────────────────────────────────
    profile_text = (
        "\n".join(f"- {k}: {v}" for k, v in user_profile.items())
        if user_profile else "(no user profile yet)"
    )

    episodic_text = (
        "\n".join(
            f"- [{ep.get('timestamp', '')[:10]}] {ep.get('summary', '')} (outcome: {ep.get('outcome', '')})"
            for ep in episodes
        )
        if episodes else "(no relevant episodes)"
    )

    semantic_text = (
        "\n".join(f"- {h}" for h in semantic_hits)
        if semantic_hits else "(no relevant knowledge chunks)"
    )

    recent_text = (
        "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in recent_turns
        )
        if recent_turns else "(conversation just started)"
    )

    # ── Budget enforcement (trim lowest priority first) ────────────────
    sections = {
        "semantic": semantic_text,
        "episodic": episodic_text,
        "profile": profile_text,
        "recent": recent_text,
    }

    total = sum(len(v) for v in sections.values())
    if total > memory_budget:
        for key in sorted(sections, key=lambda k: SECTION_PRIORITY[k]):
            excess = total - memory_budget
            if excess <= 0:
                break
            current_len = len(sections[key])
            trim_to = max(50, current_len - excess)
            sections[key] = _trim_to_budget(sections[key], trim_to)
            total = sum(len(v) for v in sections.values())

    return SYSTEM_TEMPLATE.format(
        profile_section=sections["profile"],
        episodic_section=sections["episodic"],
        semantic_section=sections["semantic"],
        recent_section=sections["recent"],
    )


def build_messages_for_api(
    system_prompt: str,
    current_input: str,
) -> tuple[str, List[dict]]:
    """
    Returns (system_prompt, messages) ready for Anthropic API.
    """
    messages = [{"role": "user", "content": current_input}]
    return system_prompt, messages