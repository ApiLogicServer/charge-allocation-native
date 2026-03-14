# How Were These Apps Built? (Non-Technical Summary)

**Same AI. Same requirements. One extra sentence. Completely different results.**

---

### What happened

| | Naive app | This app (`allo_dept_gl`) |
|---|---|---|
| **Step 1** | Ask AI for the app | Run `genai-logic create` |
| **Step 2** | Done | Load ALS context into AI |
| **Step 3** | — | Paste requirements — done |

The naive developer gave the AI a blank page.  
The ALS developer gave the AI a scaffold, a rulebook, and a running start.

---

### The analogy

Two architects. Same client brief. One works alone from scratch. The other works inside a firm with standard plans, building codes, and a crew standing by. Both deliver — but only one is move-in ready.

---

### What you get

| Question | Naive | ALS |
|---|---|---|
| Production-ready? | No — months more work | Yes — included |
| Admin UI? | No | Yes |
| Add a new rule? | Risky rewrite | One line |
| Auditable? | Partially | Yes |

---

**It's not a black box.** Everything ALS generates is standard Python — plain files that engineers read, edit, and version-control with their normal tools. The scaffold is a starting point, not a cage.

---

**The bottom line:** Neither developer wrote more than a paragraph of requirements.  
The tool — not the effort — is what made one system production-ready.
