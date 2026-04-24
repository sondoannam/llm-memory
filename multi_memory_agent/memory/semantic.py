"""
Semantic Memory — Vector Store for Knowledge Chunks
Role: Retrieves relevant facts, FAQs, or domain knowledge by semantic similarity.
Backend: ChromaDB (in-process) with TF-IDF keyword fallback.
"""

from __future__ import annotations
import math
import re
import uuid
from collections import Counter
from typing import List


# ------------------------------------------------------------------ #
#  TF-IDF Fallback (no embedding server needed)                        #
# ------------------------------------------------------------------ #

def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-ZÀ-ỹ0-9]+", text.lower())


def _tfidf_score(query_tokens: List[str], doc_tokens: List[str], corpus: List[List[str]]) -> float:
    doc_tf = Counter(doc_tokens)
    N = len(corpus) + 1
    score = 0.0
    for t in query_tokens:
        tf = doc_tf.get(t, 0) / (len(doc_tokens) + 1)
        df = sum(1 for d in corpus if t in d) + 1
        idf = math.log(N / df)
        score += tf * idf
    return score


# ------------------------------------------------------------------ #
#  SemanticMemory                                                       #
# ------------------------------------------------------------------ #

class SemanticMemory:
    """
    Stores knowledge chunks and retrieves the most relevant ones.
    Primary backend: ChromaDB.
    Fallback: in-process TF-IDF when Chroma is unavailable.
    """

    def __init__(self, collection_name: str = "agent_knowledge", use_chroma: bool = False):
        self._docs: List[dict] = []   # fallback store
        self._chroma_ok = False
        self._collection = None

        if use_chroma:
            try:
                import chromadb
                client = chromadb.Client()   # in-process, no server needed
                self._collection = client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                self._chroma_ok = True
                print("[Semantic] ChromaDB backend ready.")
            except Exception as e:
                print(f"[Semantic] ChromaDB unavailable ({e}), using TF-IDF fallback.")

    # ------------------------------------------------------------------ #
    #  Write                                                               #
    # ------------------------------------------------------------------ #

    def add(self, text: str, metadata: dict | None = None) -> str:
        doc_id = str(uuid.uuid4())[:8]
        meta = metadata or {}
        chroma_meta = meta if meta else {"_": "1"}   # Chroma rejects empty dicts

        if self._chroma_ok:
            self._collection.add(
                documents=[text],
                metadatas=[chroma_meta],
                ids=[doc_id],
            )
        # Always keep fallback copy for TF-IDF
        self._docs.append({"id": doc_id, "text": text, "meta": meta})
        return doc_id

    def add_many(self, texts: List[str], metadatas: List[dict] | None = None) -> List[str]:
        metas = metadatas or [{} for _ in texts]
        return [self.add(t, m) for t, m in zip(texts, metas)]

    # ------------------------------------------------------------------ #
    #  Read                                                                #
    # ------------------------------------------------------------------ #

    def search(self, query: str, top_k: int = 3) -> List[str]:
        if self._chroma_ok:
            try:
                results = self._collection.query(
                    query_texts=[query],
                    n_results=min(top_k, max(1, len(self._docs))),
                )
                return results["documents"][0] if results["documents"] else []
            except Exception:
                pass  # fall through to TF-IDF

        return self._tfidf_search(query, top_k)

    def _tfidf_search(self, query: str, top_k: int) -> List[str]:
        if not self._docs:
            return []
        q_tokens = _tokenize(query)
        corpus = [_tokenize(d["text"]) for d in self._docs]
        scored = [
            (_tfidf_score(q_tokens, corpus[i], corpus), self._docs[i]["text"])
            for i in range(len(self._docs))
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in scored[:top_k] if _ > 0]

    def format_for_prompt(self, hits: List[str]) -> str:
        if not hits:
            return "(no relevant knowledge chunks)"
        return "\n".join(f"- {h}" for h in hits)

    # ------------------------------------------------------------------ #
    #  Utils                                                               #
    # ------------------------------------------------------------------ #

    def clear(self) -> None:
        self._docs.clear()
        if self._chroma_ok:
            try:
                for doc in self._collection.get()["ids"]:
                    self._collection.delete(ids=[doc])
            except Exception:
                pass

    def __len__(self) -> int:
        return len(self._docs)