"""
Long-Term Profile Memory — Persistent Key-Value Store
Role: Stores stable user facts (name, preferences, allergies, goals…).
Backend: JSON file  →  drop-in replaceable with Redis (same interface).

Redis swap: replace _load/_save with redis.StrictRedis.hset/hget calls.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any


class LongTermMemory:
    """
    Flat key-value profile store with conflict resolution.
    Latest value always wins (LWW — Last-Write-Wins).
    """

    def __init__(self, storage_path: str = "/tmp/long_term_profile.json"):
        self._path = Path(storage_path)
        self._store: dict[str, Any] = self._load()

    # ------------------------------------------------------------------ #
    #  Persistence (JSON ≈ Redis HSET/HGETALL)                            #
    # ------------------------------------------------------------------ #

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._store, ensure_ascii=False, indent=2))

    # ------------------------------------------------------------------ #
    #  Write                                                               #
    # ------------------------------------------------------------------ #

    def set(self, key: str, value: Any) -> None:
        """
        Upsert a profile fact.
        If key already exists, the new value silently wins (conflict resolved).
        """
        old = self._store.get(key)
        self._store[key] = value
        self._save()
        if old is not None and old != value:
            print(f"[LongTerm] Conflict resolved: '{key}' {old!r} → {value!r}")

    def set_many(self, facts: dict[str, Any]) -> None:
        for k, v in facts.items():
            self.set(k, v)

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            self._save()
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Read                                                                #
    # ------------------------------------------------------------------ #

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def get_all(self) -> dict:
        return dict(self._store)

    def format_for_prompt(self) -> str:
        if not self._store:
            return "(no user profile)"
        lines = [f"- {k}: {v}" for k, v in self._store.items()]
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  Utils                                                               #
    # ------------------------------------------------------------------ #

    def clear(self) -> None:
        self._store.clear()
        self._save()

    def __len__(self) -> int:
        return len(self._store)

    def __repr__(self) -> str:
        return f"LongTermMemory({self._store})"