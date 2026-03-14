# Allocation Implementation Comparison: `naive_allocation3` vs `allo_dept_gl`

This document compares two implementations of the same department/GL allocation system:

| | `naive_allocation3` | `allo_dept_gl` (this project) |
|---|---|---|
| **Style** | Proof-of-concept Flask app | Production ApiLogicServer (ALS) project |
| **Size** | ~700-line `app.py` | Full project scaffold |

---

## Architecture

| Dimension | `naive_allocation3` | `allo_dept_gl` |
|---|---|---|
| **Type** | Plain Flask app | ApiLogicServer (ALS) project |
| **Structure** | Single `app.py` | `api/`, `logic/`, `database/`, `security/`, `ui/`, `devops/`, … |
| **API** | Hand-rolled `@app.route` CRUD | SAFRS JSON:API (auto-generated from models) |
| **UI** | One `templates/index.html` | Full Admin App (auto-generated) |

---

## Data Model — Same Core Concept, Richer in ALS

Both implement the same two-level allocation hierarchy:

```
Project → Charge
  └─ ProjectFundingDef → ProjectFundingLine (dept + charge-def + percent)
       └─ DeptChargeDef → DeptChargeDefLine (gl_account + percent)
```

| Aspect | `naive_allocation3` | `allo_dept_gl` |
|---|---|---|
| **Table naming** | `snake_case` | `PascalCase` |
| **GLAccount fields** | `account_number`, `description` | `account_code`, `name` |
| **ChargeDeptAllocation** | charge + dept + charge_def + percent/amount | adds `project_funding_line_id` FK directly |
| **ChargeGlAllocation** | dept_alloc + gl_account + percent/amount | adds `dept_charge_def_line_id` FK directly |
| **Project** | no status column | `status` (`proposed` / `active` / `complete`) |
| **Charge** | project, description, amount | adds `source`, `match_confidence`, `match_notes`, `needs_review` |
| **Extra tables** | none | `SysConfig` (runtime rates/limits), `SysChargeMatchReq` (AI matching audit trail) |

---

## Business Logic — The Core Difference

### `naive_allocation3` — Imperative Python

All logic lives inside route handlers and model methods:

- `DeptChargeDefinition.recalculate()` — called **manually** in every route handler after each line insert, update, or delete.
- `ProjectFundingDefinition.recalculate()` — same pattern.
- `allocate_charge()` — called explicitly **only** from the `POST /charges` handler.  
  ⚠️ If a charge's `amount` is later updated, allocations are **not** recalculated.

**Risk:** Any new endpoint, script, or import that modifies data and doesn't call `recalculate()` or `allocate_charge()` will silently leave the database in an inconsistent state.

---

### `allo_dept_gl` — Declarative LogicBank Rules (`logic/logic_discovery/allocation.py`)

| Rule | What it does |
|---|---|
| `Rule.sum` | `DeptChargeDef.total_percent` and `ProjectFundingDef.total_percent` recalculate **automatically** whenever any child line is inserted, updated, or deleted — regardless of which endpoint triggered the change |
| `Rule.formula` | `is_active` re-derives whenever `total_percent` changes |
| `Rule.constraint` | Blocks posting a `Charge` to a non-active project or incomplete Funding Definition; also validates `project.status == 'active'` |
| `Rule.copy` / `Rule.formula` | Re-derive `ChargeDeptAllocation.amount` and `ChargeGlAllocation.amount` even when `Charge.amount` is **updated** after creation |
| `Allocate` (Level 1) | `Charge → ChargeDeptAllocation`: one allocation row per `ProjectFundingLine` |
| `Allocate` (Level 2) | `ChargeDeptAllocation → ChargeGlAllocation`: one row per `DeptChargeDefLine` |

**Benefit:** Rules fire for every database change — via the API, admin UI, test scripts, or bulk imports — with no extra code required.

---

## Extra Features in `allo_dept_gl`

| Feature | Description |
|---|---|
| **AI charge matching** | `Rule.early_row_event` on `Charge` calls an LLM to match unassigned charges to projects; results stored in `SysChargeMatchReq` for audit |
| **Optimistic locking** | Prevents lost updates when two users edit the same record simultaneously |
| **Security / grants** | Role-based access control in `security/` |
| **Kafka integration** | Event streaming in `integration/kafka/` |
| **`SysConfig` table** | One-row table for runtime-configurable `discount_rate`, `tax_rate` — change rates without a code deploy |

---

## Talking Points for a Non-Technical Manager

### What problem are we solving?

Both systems allocate a project charge across departments and GL accounts based on predefined percentage splits. They produce the same result. The question is: which approach is safer, faster to extend, and cheaper to maintain over time?

---

### What is the main difference?

Think of the naive approach like a **manual spreadsheet with macros**: it works when you remember to run the macro, but if anyone edits a cell without running it, the totals go wrong — and you won't know until someone audits.

The ALS approach is like a **spreadsheet with live formulas**: change any number anywhere, and every total updates instantly and automatically. There is no "forgetting to recalculate."

---

### Key talking points

1. **Correctness is guaranteed, not assumed.**  
   In the naive approach, keeping allocations correct requires every developer, every script, and every data migration to manually call the right functions. In ALS, the rules fire automatically for every database change, no matter where it comes from. This dramatically reduces the risk of silent data corruption.

2. **Less code to write, less code to break.**  
   The naive app has ~700 lines of boilerplate CRUD routes. The ALS version replaces all of that with auto-generated API endpoints. Developers focus on business logic, not plumbing. Fewer lines of hand-written code means fewer places for bugs to hide.

3. **Faster to extend.**  
   Need to add a new rule — say, "a charge over $50,000 must be flagged for manager approval"? In ALS, that's one declarative `Rule.constraint` line. In the naive approach, you'd need to find and patch every route that creates or updates a charge.

4. **Built-in AI charge matching.**  
   The ALS version can automatically match incoming charges to the right project using an AI model, with a full audit trail. This alone can save significant manual review time for high-volume charge entry.

5. **Runtime configuration without a code deployment.**  
   The `SysConfig` table lets a business user change a discount rate or tax rate without involving a developer. In the naive app, that requires a code change and a deployment.

6. **Professional-grade features out of the box.**  
   ALS includes role-based security, optimistic locking (preventing "last writer wins" data loss), an admin UI, and API documentation — all without writing a line of extra code.

---

### When would you choose the naive approach?

- A **one-time, throwaway prototype** to validate the data model over a weekend.
- A **single-developer project** with no risk of parallel editing or bulk imports.
- When you need something running in hours and plan to replace it in days.

---

### When would you choose the ALS approach?

- Any system that will go to **production** or be used by real users.
- Any system where **data integrity matters** (finance, compliance, audit).
- Any system that will be **maintained or extended** over months or years.
- Any system with **multiple data entry paths** (API, admin UI, test scripts, imports).
- Any system where you want to **add AI-assisted features** (matching, categorization, flagging) without starting from scratch.

---

### Bottom line

The naive prototype got us to a working model quickly — that was its job. The ALS version takes that model and makes it production-ready: correct by construction, easier to extend, and significantly cheaper to maintain. For a real allocation system handling real money, the ALS approach is the responsible choice.

---

# Talking Points for a Non-Technical Manager: How Were These Apps Built?

### Both apps came from nearly the same description

A developer wrote a plain-English description of the allocation system — departments, GL accounts, and the rules for splitting a project charge. Both developers gave that same description to an AI assistant. The only difference was one extra sentence in the naive version asking for a web page.

Same AI. Nearly the same words. Completely different results.

---

### So why are the results so different?

The difference is not in *what was asked*. It's in *what the AI was working with*.

Think of it like hiring two architects. You give both the same brief. One works alone, starting from a blank page. The other works inside a firm that has established building codes, standard floor plans, approved materials lists, and a construction crew standing by. Both produce a design from your brief — but one is move-in ready and the other is a sketch that still needs structural engineering, permits, plumbing, and electrical.

For the `allo_dept_gl` project, before the AI saw a single word of the requirements, the developer ran one command:

```bash
genai-logic create --project_name=allo_dept_gl --db_url=sqlite:///samples/dbs/starter.sqlite
```

That command set up the entire project structure — API, Admin UI, security, deployment, logic hooks — around a nearly empty starter database. Then the developer loaded the ALS context (the "firm's building codes") into the AI assistant and pasted the requirements. The AI, now aware of how ALS projects work, produced a complete, production-ready system in one prompt.

The naive developer skipped the setup command, gave the AI no context about any framework, and asked for everything at once. The AI did its best — and produced a standalone script.

---

### What this means in practice

| Question | Naive app | ALS app (this project) |
|---|---|---|
| How long did it take? | One AI conversation | One command + one AI conversation |
| How long to make it production-ready? | Months of additional custom development | Already included |
| What happens when requirements change? | Developer manually edits code throughout | Re-run the setup; rules stay in place |
| Can a non-developer browse the data? | No — requires a developer to add UI | Yes — Admin UI is built in |
| Is it auditable? | Partially | Yes — AI matching decisions, charge history, and security grants are all tracked |
| Can we add a new rule without a major rewrite? | Risky — must find every affected code path | Low-risk — one line in the rules file |

---

### The key insight

Neither developer wrote more than a paragraph of requirements. The naive app proves the idea can be modeled. The ALS app proves it can be *deployed*. The difference is that ALS tools gave the AI the context to go from requirements to production in a single conversation — the same way a builder with the right tools and blueprints moves faster than one starting from scratch.

---

## Talking Points for a Technical Manager: How Were These Apps Built?

### The prompt was nearly identical — the context was not

Both applications started from essentially the same natural language requirements: departments, GL accounts, charge definitions, funding definitions, and a two-level cascade allocation. The only prompt difference was that `naive_allocation3` needed **one extra sentence** requesting a web interface.

The workflows, however, were completely different:

**`naive_allocation3`:**
```
LLM prompt (vanilla AI, no framework context) → monolithic app.py
```

**`allo_dept_gl`:**
```bash
# Step 1: one CLI command — creates the full ALS project scaffold
genai-logic create --project_name=allo_dept_gl --db_url=sqlite:///samples/dbs/starter.sqlite

# Step 2: load ALS context into the AI assistant
# (paste into Copilot: "Please load .github/.copilot-instructions.md")

# Step 3: paste the requirements prompt — one time, done
```

That's it. `starter.sqlite` contained only a single `SysConfig` table. `genai-logic create` built the entire project scaffold around it. Loading the copilot instructions gave the AI assistant full knowledge of ALS patterns — LogicBank rules, SAFRS API, model conventions, admin app setup. The requirements prompt then drove the AI to design the schema, generate models, write declarative rules, and configure the admin app — all within one conversation, guided by the framework context.

The naive approach gave the AI no framework context. The AI made every architectural decision itself, producing a standalone script with no upgrade path.

---

### What `genai-logic create` did automatically (from a 1-table starter schema)

When `allo_dept_gl` was created with `genai-logic create`, the following were generated **without any additional prompting or hand-coding**:

| Generated artifact | How you'd get it in the naive approach |
|---|---|
| Full JSON:API (50+ endpoints, filtering, sorting, pagination) | Write ~700 lines of `@app.route` code by hand |
| Admin UI (browse, search, edit all tables) | Build a separate front-end application |
| `database/models.py` (SQLAlchemy ORM with typed relationships) | Write manually or reverse-engineer |
| `logic/declare_logic.py` scaffold (LogicBank hooks) | No equivalent exists |
| `security/` (authentication, role-based access) | Write from scratch |
| `devops/` (Docker compose, deployment configs) | Write from scratch |
| `integration/kafka/` (event streaming stubs) | Write from scratch |
| Optimistic locking | Write from scratch |
| API documentation | Write from scratch or add a library |

The naive app has none of these. It has CRUD routes and an allocation function.

---

### The compounding gap: logic maintainability

The naive app's business logic (the `recalculate()` calls and `allocate_charge()`) is scattered across route handlers. Every new endpoint is a potential place where a developer forgets to call them. Over time this gap widens:

- Add a bulk-import endpoint → developer must remember to call `recalculate()`
- Add a test-data loader → same
- Add a CLI migration script → same

In `allo_dept_gl`, the `Rule.sum`, `Rule.formula`, and `Allocate` declarations in `logic/logic_discovery/allocation.py` fire for **every** database mutation regardless of origin. The developer writes the rule once; the framework enforces it everywhere.

This is not a small quality-of-life difference. For a financial system, it's the boundary between "probably correct" and "provably correct."

---

### Developer productivity comparison

| Activity | `naive_allocation3` | `allo_dept_gl` (via `genai-logic create`) |
|---|---|---|
| **Setup before AI conversation** | None | `genai-logic create` + load copilot instructions |
| **AI context provided** | None (vanilla LLM) | Full ALS framework context via `.github/.copilot-instructions.md` |
| **Number of prompts to working system** | 1 (+ web UI sentence) | 1 |
| **Result of that prompt** | Monolithic `app.py` — no path to production | Full ALS project: API, Admin UI, logic scaffold, security, devops |
| **Regenerating after schema change** | Manually edit routes, models, and HTML | `rebuild-from-database` → entire scaffold regenerates |
| **Time to working Admin UI** | Hours to days (custom HTML/JS) | Zero — included |
| **Adding a new constraint** | Find every relevant route, add validation | One `Rule.constraint` line |
| **Adding a new derived field** | Add to model + call site in every handler | One `Rule.formula` line |
| **Handling amount updates** | Bug — not handled in naive impl | Covered by existing `Rule.formula` |
| **Security** | Not implemented | Role-based grants in `security/` |
| **Onboarding a new developer** | Read 700 lines of interleaved logic and routing | Logic is isolated in `logic/logic_discovery/` |

---

### The context gap amplifies over time

The naive approach gave the AI a blank slate. The AI solved the immediate problem by producing one self-contained file. That's appropriate for a prototype — but every future change requires a developer to manually locate and update the relevant routes, model methods, and HTML. There is no scaffold to regenerate, no rule engine to extend, no security layer to configure.

The ALS approach gave the AI a framework and a scaffold. The AI produced rules, not routes — and rules compose. Adding a new constraint, a new derived field, or a new allocation level costs one declaration instead of a surgery on interleaved application code.

---

### Bottom line for a technical manager

Two developers, same requirements, same AI assistant. One typed one extra sentence and got a working script. The other ran one CLI command, loaded the ALS context, pasted the same prompt, and got a production-ready system — JSON:API, Admin UI, declarative rules, security, devops, and Kafka stubs included.

The difference was not effort or skill. It was **context**. `genai-logic create` gave the AI a scaffold to build into. The copilot instructions gave the AI the patterns to follow. Without those, the AI makes reasonable architectural guesses — and those guesses close off future options.

For any project that will outlive the first sprint, run `genai-logic create` first. It costs one command and eliminates entire categories of technical debt before the first line of business logic is written.
