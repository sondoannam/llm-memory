"""
Short-Term Memory — Sliding Window Conversation Buffer
Role: Holds the most recent N turns so the agent never loses immediate context.
Backend: In-memory list (mimics LangChain ConversationBufferMemory).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass
class Message:
    role: str   # "user" | "assistant"
    content: str
    token_estimate: int = field(init=False)

    def __post_init__(self):
        # Rough estimate: 1 token ≈ 4 chars
        self.token_estimate = max(1, len(self.content) // 4)


class ShortTermMemory:
    """
    Fixed-size sliding window over the raw conversation.
    Evicts oldest turns first when the token budget is exceeded.
    """

    def __init__(self, max_turns: int = 10, max_tokens: int = 2_000):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self._buffer: List[Message] = []

    # ------------------------------------------------------------------ #
    #  Write                                                               #
    # ------------------------------------------------------------------ #

    def add(self, role: str, content: str) -> None:
        self._buffer.append(Message(role=role, content=content))
        self._evict()

    def _evict(self) -> None:
        """Remove oldest messages until within turn and token limits."""
        while len(self._buffer) > self.max_turns * 2:   # pairs
            self._buffer.pop(0)

        while self._token_count() > self.max_tokens and len(self._buffer) > 2:
            self._buffer.pop(0)   # drop oldest

    def _token_count(self) -> int:
        return sum(m.token_estimate for m in self._buffer)

    # ------------------------------------------------------------------ #
    #  Read                                                                #
    # ------------------------------------------------------------------ #

    def get_recent(self, n_turns: int | None = None) -> List[dict]:
        """Return the last n_turns (user+assistant pairs) as plain dicts."""
        msgs = self._buffer
        if n_turns is not None:
            msgs = msgs[-(n_turns * 2):]
        return [{"role": m.role, "content": m.content} for m in msgs]

    def format_for_prompt(self) -> str:
        """Human-readable block for prompt injection."""
        if not self._buffer:
            return "(no recent conversation)"
        lines = []
        for m in self._buffer:
            prefix = "User" if m.role == "user" else "Assistant"
            lines.append(f"{prefix}: {m.content}")
        return "\n".join(lines)

    def clear(self) -> None:
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)

    @property
    def token_count(self) -> int:
        return self._token_count()