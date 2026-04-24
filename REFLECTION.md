# REFLECTION.md — Privacy, Limitations & Design Tradeoffs

## 1. Which memory layer helped the agent most?

**Long-term profile memory** delivered the clearest improvement. Once the agent knows a user's name, allergy, or job role, every subsequent response becomes personalised without the user needing to repeat themselves. The delta between no-memory and with-memory is most visible in scenario 1 (name recall after 6 turns) and scenario 10 (full integration), where the no-memory baseline either guesses wrong or asks for clarification.

**Semantic memory** was the second biggest win for knowledge-heavy queries. Without it, the agent answers FAQ questions from training data alone, which may be stale or wrong. With seeded chunks, the answer is grounded in the operator's actual documentation.

---

## 2. Which memory layer is riskiest if retrieved incorrectly?

**Long-term profile memory** is highest risk:
- It stores PII directly: name, age, allergy, health conditions, job.
- A wrongly retrieved or stale allergy fact (`milk` instead of `soy`) could cause real harm if the agent is used in a health or food context.
- The LWW conflict resolution is simple but correct *only if the last write is always the right one* — adversarial users could overwrite facts deliberately.

**Episodic memory** is second: it stores summaries of past interactions. If an episode from a different user is retrieved (e.g., shared session ID collision), private information leaks across users.

---

## 3. If the user requests memory deletion, what gets deleted where?

| Memory layer | Deletion method | Notes |
|---|---|---|
| Short-term | `short_term.clear()` | In-memory, instant |
| Long-term profile | `long_term.delete(key)` or `long_term.clear()` | JSON file; production: Redis `DEL` or `HDEL` |
| Episodic | `episodic.clear()` | JSON file; no granular per-fact delete yet |
| Semantic | `semantic.clear()` | Removes all chunks; no per-document delete in TF-IDF fallback |

**Gap:** There is no user-facing "forget everything about me" command yet. A production system needs a `right_to_erasure()` method that cascades across all 4 backends atomically.

---

## 4. PII and Privacy Risks

### Risk 1: Plaintext PII in profile store
The JSON profile file on disk contains raw PII (name, allergies, job). Anyone with filesystem access can read it. **Mitigation:** encrypt at rest using `cryptography` library; use Redis ACLs in production.

### Risk 2: No consent gate
The agent silently extracts and stores facts from every user message. Users are not told that "Tôi tên là Linh" will be persisted. **Mitigation:** surface a consent banner on first use; offer opt-out for long-term storage.

### Risk 3: No TTL on profile facts
A fact written today never expires. If a user's allergy changes and they don't explicitly correct it, the old value persists forever. **Mitigation:** add `written_at` timestamp; expire facts after 90 days.

### Risk 4: Episodic log grows unbounded
The episodic log appends forever. Over time it contains a detailed history of everything the user ever asked. **Mitigation:** rolling window (keep last 200 episodes); anonymise summaries before archival.

### Risk 5: Semantic memory is shared
In the current design, all users share the same semantic store. A user who seeds harmful content could affect all other users. **Mitigation:** namespace semantic collections per tenant; validate chunks before insertion.

---

## 5. Technical Limitations of the Current Solution

### Limitation 1: Rule-based intent classifier
The router uses keyword matching to classify intent. It will misclassify queries that don't contain the expected keywords (e.g., "quên mất, mình thích gì nhỉ?" — episodic+profile, but no trigger words). **Fix:** replace with a small LLM call or a trained classifier.

### Limitation 2: TF-IDF semantic retrieval
TF-IDF has no semantic understanding — "Docker container networking" and "how microservices talk to each other" are unrelated by TF-IDF but semantically identical. **Fix:** use Chroma with a proper embedding model (Chroma works when the ONNX model is available).

### Limitation 3: Fact extraction is English/Vietnamese keyword-only in mock mode
The mock extractor uses regex, which fails on complex sentences. The LLM extractor works but costs an extra API call per turn. **Fix:** use structured output / tool calling in the main LLM call to extract facts in one pass.

### Limitation 4: No cross-session identity
Session IDs are generated randomly. If the same user opens a new tab, they get a blank profile. **Fix:** implement user authentication and tie session_id to a stable user ID.

### Limitation 5: Scale bottleneck
The episodic store is a flat JSON file with linear keyword search (O(n)). At 10,000 episodes, search becomes the bottleneck. **Fix:** migrate to SQLite with FTS5 (free, no server), or Elasticsearch for production scale.

### Limitation 6: LWW conflict resolution is too simple
Last-Write-Wins works for simple corrections ("my allergy changed") but fails for additive facts ("I am also allergic to nuts"). **Fix:** use a CRDT-style merge or ask the LLM to reconcile contradictory facts.

---

## Summary

| Question | Answer |
|---|---|
| Most helpful memory | Long-term profile |
| Most dangerous if wrong | Long-term profile (PII + health facts) |
| Deletion scope | All 4 backends; needs `right_to_erasure()` |
| PII risk | Yes — name, age, health; needs encryption + consent |
| Top scale bottleneck | Episodic flat JSON; migrate to FTS5/Elasticsearch |