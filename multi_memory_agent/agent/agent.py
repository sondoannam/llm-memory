"""
MemoryAgent — Entry point for the multi-memory LLM agent.
"""

from typing import List
from ..memory import ShortTermMemory, LongTermMemory, EpisodicMemory, SemanticMemory
from .graph import build_graph


class MemoryAgent:
    """
    Agent exposing chat() and seed_knowledge() interface.
    Initializes memory and LangGraph graph.
    """

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id

        # Initialize the 4 memory tiers
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(storage_path=f"/tmp/{session_id}_profile.json")
        self.episodic = EpisodicMemory(storage_path=f"/tmp/{session_id}_episodic.json")
        self.semantic = SemanticMemory(collection_name=f"{session_id}_semantic", use_chroma=False)

        self._app = build_graph(
            self.short_term,
            self.long_term,
            self.episodic,
            self.semantic
        )

    def seed_knowledge(self, knowledge: List[str]):
        """Inject domain knowledge into Semantic Memory."""
        if knowledge:
            self.semantic.add_many(knowledge)

    def chat(self, user_input: str) -> str:
        """
        Send a message to the agent and get its response.
        Updates memory as a byproduct.
        """
        initial_state = {
            "messages": [{"role": "user", "content": user_input}],
            "current_input": user_input,
            "session_id": self.session_id,
        }
        final_state = self._app.invoke(initial_state)
        return final_state["response"]

    def memory_summary(self) -> str:
        """Helper to get memory counts."""
        return (
            f"ST: {len(self.short_term)} turns | "
            f"LT: {len(self.long_term)} facts | "
            f"EP: {len(self.episodic)} eps | "
            f"SEM: {len(self.semantic)} chunks"
        )
