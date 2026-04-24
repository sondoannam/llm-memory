"""
Episodic Memory — Chronological Log of Task Episodes
Role: Remembers *what happened* in past sessions (outcome, context, lesson).
Backend: JSON append-only log file.

Each episode = one meaningful task the agent helped complete.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List


class Episode:
    def __init__(
        self,
        summary: str,
        outcome: str,
        tags: list[str] | None = None,
        session_id: str = "",
    ):
        self.summary = summary
        self.outcome = outcome       # "success" | "failure" | "partial"
        self.tags = tags or []
        self.session_id = session_id
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "outcome": self.outcome,
            "tags": self.tags,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Episode":
        ep = cls(
            summary=d["summary"],
            outcome=d["outcome"],
            tags=d.get("tags", []),
            session_id=d.get("session_id", ""),
        )
        ep.timestamp = d.get("timestamp", ep.timestamp)
        return ep


class EpisodicMemory:
    """
    Append-only episode log with tag-based and keyword retrieval.
    """

    def __init__(self, storage_path: str = "/tmp/episodic_memory.json"):
        self._path = Path(storage_path)
        self._episodes: List[Episode] = self._load()

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #

    def _load(self) -> List[Episode]:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text())
                return [Episode.from_dict(d) for d in raw]
            except (json.JSONDecodeError, KeyError):
                return []
        return []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([ep.to_dict() for ep in self._episodes], ensure_ascii=False, indent=2)
        )

    # ------------------------------------------------------------------ #
    #  Write                                                               #
    # ------------------------------------------------------------------ #

    def save_episode(
        self,
        summary: str,
        outcome: str = "success",
        tags: list[str] | None = None,
        session_id: str = "",
    ) -> Episode:
        ep = Episode(summary=summary, outcome=outcome, tags=tags, session_id=session_id)
        self._episodes.append(ep)
        self._save()
        print(f"[Episodic] Saved episode: {summary[:60]}...")
        return ep

    # ------------------------------------------------------------------ #
    #  Read                                                                #
    # ------------------------------------------------------------------ #

    def search(self, query: str, top_k: int = 3) -> List[Episode]:
        """Keyword-based search over episode summaries."""
        query_words = set(query.lower().split())
        scored = []
        for ep in self._episodes:
            text = (ep.summary + " " + " ".join(ep.tags)).lower()
            score = sum(1 for w in query_words if w in text)
            if score > 0:
                scored.append((score, ep))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:top_k]]

    def get_recent(self, n: int = 5) -> List[Episode]:
        return self._episodes[-n:]

    def format_for_prompt(self, episodes: List[Episode] | None = None) -> str:
        eps = episodes if episodes is not None else self.get_recent(3)
        if not eps:
            return "(no relevant episodes)"
        lines = []
        for ep in eps:
            lines.append(
                f"- [{ep.timestamp[:10]}] {ep.summary} (outcome: {ep.outcome})"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  Utils                                                               #
    # ------------------------------------------------------------------ #

    def clear(self) -> None:
        self._episodes.clear()
        self._save()

    def __len__(self) -> int:
        return len(self._episodes)