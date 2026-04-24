# Lab #17: Multi-Memory Agent with LangGraph

A production-style AI agent with a full 4-layer memory stack, built on LangGraph.

---

## Architecture

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                    LangGraph Graph                      │
│                                                         │
│  ┌─────────────────┐                                    │
│  │  retrieve_memory│  ← Memory Router                   │
│  │                 │    classify_intent(query)          │
│  │  • Short-term   │    → profile | episodic            │
│  │  • Long-term    │       semantic | general           │
│  │  • Episodic     │                                    │
│  │  • Semantic     │                                    │
│  └────────┬────────┘                                    │
│           │ MemoryState (profile + episodes +           │
│           │ semantic_hits + recent_turns)               │
│           ▼                                             │
│  ┌─────────────────┐                                    │
│  │    call_llm     │  ← Prompt injection                │
│  │                 │    4-section system prompt         │
│  │  build_system_  │    with token budget trim          │
│  │  prompt(state)  │                                    │
│  └────────┬────────┘                                    │
│           │ response + extracted_facts + episode        │
│           ▼                                             │
│  ┌─────────────────┐                                    │
│  │   save_memory   │  ← Persistence                     │
│  │                 │    LWW conflict resolution         │
│  │  • short_term   │    episodic save on completion     │
│  │  • long_term    │                                    │
│  │  • episodic     │                                    │
│  └─────────────────┘                                    │
└─────────────────────────────────────────────────────────┘
```

## Memory Stack

| Layer | Backend | Role | Interface |
|-------|---------|------|-----------|
| Short-term | Sliding window list | Last N turns | `ShortTermMemory` |
| Long-term | JSON (Redis-compatible) | User profile facts | `LongTermMemory` |
| Episodic | JSON append log | Past task outcomes | `EpisodicMemory` |
| Semantic | TF-IDF (Chroma-ready) | Domain knowledge | `SemanticMemory` |

## Setup

```bash
pip install langgraph langchain anthropic chromadb

export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

### Interactive chat
```bash
python main.py
```

### 3-turn smoke test (mock mode, no API key needed)
```bash
python main.py demo
```

### Run full benchmark (10 scenarios)
```bash
python main.py bench
```

## LangGraph State

```python
class MemoryState(TypedDict):
    messages: List[dict]        # full chat history
    current_input: str          # latest user turn
    session_id: str

    user_profile: dict          # from LongTermMemory
    episodes: List[dict]        # from EpisodicMemory
    semantic_hits: List[str]    # from SemanticMemory
    recent_turns: List[dict]    # from ShortTermMemory

    query_intent: str           # profile | episodic | semantic | general
    memory_budget: int          # token budget for memory sections

    response: str
    extracted_facts: dict       # persisted to LongTermMemory
    episode_to_save: dict | None
```

## Memory Router Logic

```
Query intent classification (rule-based, no extra LLM call):

profile  → user name, age, allergy, preference, job, goal
episodic → lần trước, debug, resolved, lesson, yesterday
semantic → how, làm thế nào, what is, explain, FAQ, API
general  → catch-all → pulls from all backends
```

## Conflict Handling

Long-term memory uses **Last-Write-Wins** (LWW):

```
User: Tôi dị ứng sữa bò.
→ profile["allergy"] = "sữa bò"

User: À nhầm, tôi dị ứng đậu nành chứ không phải sữa bò.
[LongTerm] Conflict resolved: 'allergy' 'sữa bò' → 'đậu nành'
→ profile["allergy"] = "đậu nành"   ✓
```

## Token Budget

System prompt sections are trimmed in priority order when total exceeds budget:

```
4 (highest — keep) : recent conversation
3                  : user profile
2                  : episodic memory
1 (lowest — trim)  : semantic hits
```

## Switching to Real Backends

**Redis** (drop-in for LongTermMemory):
```python
# In long_term.py, replace _load/_save with:
import redis
r = redis.StrictRedis(host='localhost', port=6379)
r.hset('profile', mapping=self._store)
self._store = r.hgetall('profile')
```

**Chroma** (already wired in SemanticMemory):
```python
SemanticMemory(use_chroma=True)   # requires ONNX model download
```