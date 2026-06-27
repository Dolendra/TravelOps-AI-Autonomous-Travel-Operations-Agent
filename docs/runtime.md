# Context Runtime

The **Context Runtime** is responsible for loading, assembly, caching, and budget containment of prompts sent to the reasoning Large Language Models (LLMs). This prevents context-window overflow, protects against token waste, and optimizes API cost performance.

---

## 📦 Data Models

Context is represented by two structured primitives:
1. **ContextFragment**: An isolated unit of context (e.g. user memory preferences, system directives, travel policies, or active transaction metrics) stamped with a version and a TTL (Time-To-Live) expiration lease.
2. **ContextBundle**: A consolidated prompt payload (list of messages) formatted for LLM consumption, accompanied by a secure SHA-256 signature hash of its component inputs.

---

## ⚡ Cache & TTL Lease Management

To minimize API latency and token cost overhead, the **Context Cache** stores compiled bundles:
* **Lookup**: Before calling an agent, the runtime generates a SHA-256 hash of the target parameters (session, message variables, agent capabilities).
* **Lease Check**: If a cached bundle exists, the runtime verifies if its creation timestamp has exceeded its **Lease Duration**. Expired leases are automatically purged from the memory store.
* **Cache Eviction**: If cache storage thresholds are reached, the cache manager performs Least Recently Used (LRU) evictions.

---

## 🪙 Dynamic Token Budget Manager

To protect the LLM gateway against context degradation, the Context Builder enforces a **sliding token allocation budget** mapping to the caller agent's specific role requirements:

| Agent Target | Token Limit (Input) | Purpose / Scope |
| :--- | :--- | :--- |
| `intent` | **2,500** | Small window, parses incoming command string and extracts entities. |
| `support` | **6,000** | Medium window, handles user chit-chat, policies, and simple FAQ lookup. |
| `planner` | **12,000** | High window, creates and registers full custom DAG graphs. |
| `reflection` | **10,000** | High window, reads stack trace errors to self-repair failures. |

### Density Optimization Strategy
If the total text size of assembled context fragments exceeds the target budget limit:
1. The builder performs a **ranked prioritization** (e.g., system instructions and core variables are locked; conversation history is truncated).
2. The builder prunes history segments starting with the oldest index.
3. The pruned segments are logged in the session's **Explainability Map** to alert developers that context pruning occurred:
   ```json
   {
     "system_directives": "LOADED",
     "chat_history": "PRUNED (Oldest 3 turns truncated to fit 6,000 tokens limit)"
   }
   ```
