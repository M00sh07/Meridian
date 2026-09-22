# MEREDIAN

> Repository Intelligence for understanding, exploring, and safely changing software.

**Status:** Early development
**Primary users:** Developers and students working with unfamiliar repositories
**Repository:** `meredian`

---

## 1. Product Definition

Meredian is a Repository Intelligence platform.

It converts a software repository and its Git history from a collection of files into a structured, queryable representation of:

* architecture
* files and directories
* classes and functions
* imports and dependencies
* function relationships
* Git history
* code metrics
* semantic meaning
* change impact
* change risk

The core product journey is:

```text
UNDERSTAND → EXPLORE → INVESTIGATE → CHANGE SAFELY
```

### Core problem

Developers and students struggle to understand an unfamiliar codebase well enough to safely work on it.

Meredian helps users:

1. understand how a repository is structured
2. discover how components depend on each other
3. investigate how the repository evolved
4. understand what a change could affect
5. estimate the risk of a change using evidence

---

# 2. What Meredian Is NOT

Meredian is not primarily:

* an AI coding assistant
* a GitHub clone
* a generic chatbot
* a code-generation tool
* a simple RAG application
* a vector database with a chat UI
* a static code viewer

The LLM is not the source of truth.

Structured repository analysis provides the evidence.

The LLM is eventually used to reason over and explain that evidence.

---

# 3. Core Product Concepts

Meredian has five major forms of repository intelligence.

## 3.1 Structural Intelligence

Answers:

* What files exist?
* What modules exist?
* What classes/functions exist?
* How is the repository organized?
* What are the entry points?

Sources:

* filesystem
* AST
* parser
* language detection

---

## 3.2 Behavioral Intelligence

Answers:

* What calls this function?
* What does this module depend on?
* How does a request move through the system?
* What components are connected?

Sources:

* imports
* function calls
* dependency relationships
* call graph
* API relationships

---

## 3.3 Historical Intelligence

Answers:

* What changed?
* Who changed it?
* How frequently does this area change?
* Which files are hotspots?
* Why has this module changed repeatedly?

Sources:

* Git commits
* diffs
* file history
* churn
* contributors
* commit frequency
* reverts
* bug-fix signals

---

## 3.4 Quality and Risk Intelligence

Answers:

* Which areas are complex?
* Which modules are highly coupled?
* Which areas have weak testing?
* Which changes have high potential impact?
* Which areas have historically been unstable?

Sources:

* code metrics
* dependency graph
* test information
* Git history
* ML models

---

## 3.5 Semantic Intelligence

Answers:

* What does this component do?
* Where is authentication implemented?
* Where is payment retry logic?
* Explain this part of the repository.

Sources:

* source code
* documentation
* metadata
* embeddings
* retrieval
* LLM reasoning

---

# 4. Product Modes

Meredian has four primary modes.

## 4.1 Understand

Purpose: help a user learn an unfamiliar repository.

Example questions:

```text
Explain this repository.

How does authentication work?

Where is payment processing implemented?

What are the main entry points?

Which files should I understand first?
```

Potential outputs:

* repository overview
* architecture explanation
* important files
* learning path
* evidence links

---

## 4.2 Explore

Purpose: navigate relationships inside the repository.

Example questions:

```text
What depends on PaymentService?

Which functions call authenticateUser?

Show the dependency chain for checkout.

What modules use this database model?
```

Primary source:

```text
dependency graph
call graph
AST relationships
```

---

## 4.3 Investigate

Purpose: understand repository evolution.

Example questions:

```text
Why has this module changed so much?

What happened to authentication over the last three months?

Which modules are repository hotspots?

Who has changed this component most frequently?
```

Primary source:

```text
Git history
commit metadata
file history
change statistics
```

---

## 4.4 Change Safely

Purpose: estimate consequences and risk before modifying code.

Example questions:

```text
What will be affected if I change this function?

Which modules depend on this?

How risky is this change?

Has this area caused problems before?

Which tests are relevant?
```

Primary sources:

```text
dependency graph
impact analysis
Git history
code metrics
test information
ML risk model
semantic retrieval
```

---

# 5. Impact vs Risk vs Uncertainty

These are different concepts and must never be treated as interchangeable.

## Impact

How much of the repository could potentially be affected?

Possible signals:

* number of callers
* dependency count
* dependency depth
* affected modules
* affected files
* API surface
* data dependencies

---

## Risk

How likely is the change to cause a defect, regression, or unintended behavior?

Possible signals:

* historical instability
* code churn
* complexity
* test coverage
* dependency count
* change surface area
* previous bug-fix activity

---

## Uncertainty

How difficult is it to verify that the change is safe?

Possible signals:

* missing tests
* unclear dependencies
* weak observability
* poorly documented behavior
* unfamiliar/unstable areas

A future UI may expose:

```text
Impact       87
Risk         71
Uncertainty  84
```

These values must be explained by evidence.

Never present unexplained scores.

---

# 6. Definition of a Problematic Change

Git repositories do not explicitly label every commit as "problematic."

Meredian therefore uses an operational proxy.

A change may be considered problematic when it is followed within a defined time window by evidence such as:

* revert
* hotfix
* bug-fix commit affecting the same area
* regression issue
* regression pull request
* CI/test recovery signal

This is a proxy label, not ground truth.

The documentation and ML implementation must explicitly acknowledge this limitation.

---

# 7. Change Risk Prediction

The ML system eventually predicts the likelihood that a change will lead to a problematic follow-up event.

Potential features:

```text
files_changed
lines_added
lines_deleted
functions_changed
classes_changed
modules_changed
cyclomatic_complexity_delta
dependency_delta
number_of_callers
dependency_count
modules_affected
api_dependencies
data_dependencies
code_churn
historical_change_frequency
historical_bug_frequency
test_coverage
tests_affected
integration_test_presence
ci_signals
```

Do not assume every feature will be available for every repository.

The feature pipeline must handle missing data explicitly.

---

# 8. Change Surface Area

Raw lines changed are not sufficient.

A change affecting:

```text
1 file
500 lines
```

may be less risky than:

```text
12 files
40 lines
8 modules
3 public APIs
```

Meredian should therefore use **change surface area** as a higher-level concept.

Potential dimensions:

```text
files
symbols
modules
dependencies
callers
APIs
data models
tests
```

---

# 9. System Architecture

Initial architecture:

```text
                    GitHub
                       │
                       ▼
              Repository Ingestion
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      AST Parser    Git Parser   Docs Parser
          │            │            │
          └────────────┼────────────┘
                       ▼
              Repository Database
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      PostgreSQL     pgvector     Graph Data
       metadata      semantic     relationships
                       │
                       ▼
               Analytics Engine
                  ┌────┴────┐
                  ▼         ▼
             Code Metrics   ML
                            │
                            ▼
                       Risk Model
                            │
                            ▼
                     Agent / LLM
                            │
                            ▼
                     Next.js UI
```

---

# 10. Technology Stack

## Frontend

```text
Next.js
TypeScript
Tailwind CSS
shadcn/ui
React Flow
```

Use D3 only where React Flow is insufficient.

---

## Backend

```text
Python
FastAPI
```

---

## Repository Analysis

```text
Tree-sitter
GitPython
```

Tree-sitter is the preferred parser because Meredian needs syntax-aware analysis rather than text-only processing.

---

## Database

```text
PostgreSQL
pgvector
```

Do not introduce a separate graph database during the initial implementation.

Graph relationships can initially be represented using PostgreSQL relational tables.

---

## Machine Learning

Initial:

```text
scikit-learn
```

Potential later models:

```text
Random Forest
XGBoost
LightGBM
```

Start with interpretable baselines.

---

## AI / LLM

The exact provider/model is intentionally not hardcoded into the architecture.

LLMs should sit above the analytical systems.

The system must work without requiring an LLM for core repository analysis.

---

# 11. LLM Architecture Principle

The LLM must not directly "guess" repository facts.

Preferred flow:

```text
User Question
     │
     ▼
LLM / Agent
     │
     ▼
Tool Selection
     │
     ├── search_code()
     ├── get_dependencies()
     ├── get_callers()
     ├── get_architecture()
     ├── get_git_history()
     ├── get_code_metrics()
     ├── predict_change_risk()
     └── get_impact_analysis()
     │
     ▼
Evidence
     │
     ▼
LLM Synthesis
     │
     ▼
Answer + Evidence + Visualization
```

The model should retrieve evidence before making repository-specific claims.

---

# 12. RAG Architecture

RAG is one component of Meredian, not the product itself.

Repository content should be split into meaningful semantic units.

Possible units:

```text
function
class
module
documentation section
API definition
configuration section
issue
pull request
commit description
```

Each embedding should contain metadata.

Example:

```json
{
  "repository": "owner/repository",
  "file": "src/auth/AuthService.ts",
  "symbol": "authenticateUser",
  "type": "function",
  "language": "typescript",
  "module": "authentication",
  "start_line": 42,
  "end_line": 81
}
```

Retrieval should eventually combine:

```text
semantic similarity
+
metadata filtering
+
graph relationships
+
repository context
```

Do not rely only on vector similarity.

---

# 13. Repository Data Model

Core entities:

```text
Repository
File
Symbol
Module
Dependency
Call
Commit
Change
Metric
Embedding
RiskPrediction
```

Conceptual relationships:

```text
Repository
 ├── Files
 │    └── Symbols
 │         ├── Calls
 │         └── Dependencies
 │
 ├── Commits
 │    └── Changes
 │
 ├── Metrics
 │
 ├── Embeddings
 │
 └── Risk Predictions
```

---

# 14. Initial Database Tables

The initial schema should evolve only when required.

Expected core tables:

```text
repositories
files
symbols
dependencies
calls
commits
changes
metrics
embeddings
risk_predictions
```

Avoid creating tables for speculative features.

---

# 15. Repository Ingestion

The first real product pipeline is:

```text
GitHub URL
    ↓
Validate URL
    ↓
Clone repository
    ↓
Discover files
    ↓
Detect languages
    ↓
Parse supported source files
    ↓
Extract symbols
    ↓
Extract imports/dependencies
    ↓
Store metadata
```

The ingestion system must:

* ignore `.git`
* respect ignore files where appropriate
* avoid secrets
* avoid generated/build directories when detectable
* handle unsupported languages gracefully
* report parser failures
* avoid crashing because one file cannot be parsed

---

# 16. AST Analysis

AST analysis should initially extract:

```text
functions
classes
methods
imports
exports
variables where useful
function calls where reliably available
```

Every extracted symbol should preserve source location:

```text
file
start_line
end_line
symbol_name
symbol_type
language
```

Source locations are important because future UI features will link analysis results back to actual code.

---

# 17. Dependency Graph

The dependency graph should represent relationships such as:

```text
File A
  └── imports → File B

Function A
  └── calls → Function B

Module A
  └── depends_on → Module B
```

Graph analysis will later support:

* callers
* callees
* upstream dependencies
* downstream dependencies
* dependency depth
* impact traversal
* architecture visualization

Do not use an LLM to infer basic import relationships that can be extracted deterministically.

---

# 18. Git Intelligence

Git analysis will eventually extract:

```text
commit SHA
author
timestamp
message
files changed
lines added
lines deleted
renamed files
deleted files
modified files
```

Derived metrics:

```text
file churn
commit frequency
change frequency
contributors
historical hotspots
reverts
bug-fix signals
```

Git history is evidence, not proof of causality.

---

# 19. Code Metrics

Potential metrics:

```text
lines of code
cyclomatic complexity
number of functions
number of classes
dependency count
fan-in
fan-out
test coverage when available
change frequency
```

Metrics should be calculated deterministically wherever possible.

---

# 20. ML Development

The ML pipeline should eventually be:

```text
Historical Repository Data
          ↓
Feature Engineering
          ↓
Change-Level Dataset
          ↓
Proxy Labels
          ↓
Train / Validation / Test
          ↓
Baseline Model
          ↓
Evaluation
          ↓
Calibration
          ↓
Risk Prediction API
```

Initial models:

1. Logistic Regression
2. Random Forest
3. XGBoost or LightGBM if justified

Metrics:

```text
Precision
Recall
F1
ROC-AUC
Calibration
```

Do not optimize only for accuracy.

Problematic changes may be a minority class.

---

# 21. ML Evaluation Rules

Avoid data leakage.

A future implementation should use chronological splitting where appropriate.

Do not randomly mix future commits into training data if the model is intended to predict future change risk.

The evaluation should reflect the real prediction scenario:

```text
Past repository history
        ↓
Train
        ↓
Predict future changes
```

---

# 22. Agent Tools

The eventual agent should have explicit tools.

Potential tools:

```text
search_code
get_file
get_symbol
get_dependencies
get_callers
get_callees
get_architecture
get_git_history
get_change_history
get_code_metrics
get_impact_analysis
predict_change_risk
get_related_tests
```

Tools should return structured evidence.

Avoid returning unnecessarily large source files when a smaller relevant range is sufficient.

---

# 23. Context Efficiency Rules

Meredian is specifically designed to minimize unnecessary LLM context usage.

### Rule 1 — Retrieve narrowly

Do not send an entire repository to an LLM.

Retrieve:

```text
relevant symbols
relevant files
relevant graph paths
relevant commits
relevant metrics
```

---

### Rule 2 — Prefer structured data

Prefer:

```json
{
  "symbol": "authenticateUser",
  "callers": 4,
  "callees": 7,
  "files_affected": 3
}
```

over dumping hundreds of lines of code.

---

### Rule 3 — Summarize before expanding

Use hierarchical retrieval:

```text
Repository summary
      ↓
Module summary
      ↓
Relevant file
      ↓
Relevant symbol
      ↓
Relevant source lines
```

Only expand when necessary.

---

### Rule 4 — Tool outputs must be bounded

Every analytical tool should support limits such as:

```text
limit
depth
top_k
max_tokens
file_count
commit_count
```

---

### Rule 5 — Do not duplicate evidence

If the graph already says:

```text
A → B → C
```

do not also provide redundant textual descriptions of the same relationship unless required.

---

### Rule 6 — Use IDs

Large objects should be referenced using stable IDs instead of repeatedly transmitting full objects.

---

### Rule 7 — Separate retrieval from synthesis

Tools retrieve facts.

The LLM explains them.

---

# 24. AI Coding Agent Rules

Any AI coding agent working on Meredian must follow these rules.

### Before coding

1. Read `MEREDIAN.md`.
2. Inspect the relevant existing code.
3. Identify the smallest required change.
4. Do not redesign unrelated systems.

### While coding

* Follow existing conventions.
* Avoid unnecessary dependencies.
* Avoid speculative abstractions.
* Do not implement future phases.
* Do not modify unrelated files.
* Prefer simple implementations.
* Preserve type safety.
* Handle errors explicitly.

### After coding

Run the relevant tests/checks.

Report:

```text
Changed
Tested
Known limitations
```

---

# 25. Phase Roadmap

## Phase 0 — Foundation

Goal:

```text
Working monorepo
Frontend
FastAPI backend
Health endpoint
Documentation
```

No AI.

No database.

No ML.

No authentication.

---

## Phase 1 — Repository Understanding

Goal:

> A user can provide a repository URL and Meredian can build a basic structured representation.

Implement:

* GitHub URL ingestion
* repository cloning
* file discovery
* language detection
* AST parsing
* symbol extraction
* basic metadata storage
* repository explorer

Success condition:

```text
Repository URL
      ↓
Repository structure
      ↓
Files
      ↓
Symbols
```

---

## Phase 2 — Repository Graph

Implement:

* imports
* dependencies
* function calls
* callers
* callees
* dependency traversal
* graph visualization

Success condition:

```text
"What depends on X?"
```

can be answered deterministically.

---

## Phase 3 — Git Intelligence

Implement:

* commit ingestion
* file history
* churn
* contributors
* modification frequency
* historical hotspots
* change history

Success condition:

```text
"Why has this module changed so much?"
```

has evidence from Git history.

---

## Phase 4 — Semantic Intelligence

Implement:

* chunking
* embeddings
* pgvector
* semantic retrieval
* metadata filtering
* hybrid retrieval

Success condition:

```text
"Where is payment retry logic?"
```

returns relevant implementation evidence.

---

## Phase 5 — Change Impact

Implement:

* diff ingestion
* changed symbol detection
* dependency traversal
* affected modules
* affected tests
* impact scoring

Success condition:

```text
"What will this change affect?"
```

returns a traceable impact analysis.

---

## Phase 6 — ML Risk Prediction

Implement:

* historical dataset construction
* proxy labels
* feature engineering
* baseline models
* evaluation
* prediction API
* explanations

Success condition:

```text
"How risky is this change?"
```

returns a model prediction supported by features/evidence.

---

## Phase 7 — Agentic Intelligence

Connect:

```text
RAG
Graph
Git
Metrics
ML
```

through explicit tools.

The agent should be able to answer complex questions by combining multiple evidence sources.

---

## Phase 8 — Product Polish

Implement:

* architecture visualization
* repository dashboard
* code viewer
* Git timeline
* change impact view
* risk dashboard
* evidence panels
* loading states
* error states
* authentication if required
* deployment
* documentation

---

# 26. UI Principles

Meredian should feel like a serious developer tool.

Avoid:

* generic AI chat landing pages
* excessive gradients
* unnecessary glassmorphism
* huge hero sections
* generic SaaS dashboards
* "AI-powered" everywhere
* decorative animations with no purpose

Prioritize:

* information density
* clear hierarchy
* code readability
* graph visualization
* evidence
* interaction
* fast navigation
* progressive disclosure

The UI should make complex repository information understandable without hiding the underlying evidence.

---

# 27. Core UI

Potential structure:

```text
Meredian
│
├── Repository Overview
│
├── Explorer
│   ├── Files
│   ├── Symbols
│   └── Code
│
├── Architecture
│   └── Dependency Graph
│
├── History
│   ├── Commits
│   ├── Hotspots
│   └── Churn
│
├── Changes
│   ├── Impact
│   └── Risk
│
└── Investigate
    └── AI interface
```

---

# 28. Evidence-First Design

Every important AI-generated claim should be traceable to evidence.

Example:

```text
AuthenticationService appears to be a high-risk module.

Evidence:
• 14 changes in the last 90 days
• 3 bug-fix commits
• 8 downstream dependents
• 62% test coverage
• high cyclomatic complexity
```

Do not produce:

```text
This module is risky because the AI thinks it is risky.
```

---

# 29. Security

Repository source code may contain sensitive information.

Never:

* expose environment variables
* log secrets
* store API keys in repository analysis
* send unnecessary source code to external LLM providers
* assume repositories are public
* expose one user's repository to another user

Future implementation must define:

* secret filtering
* repository isolation
* access control
* data retention
* deletion
* provider data handling

---

# 30. Error Handling

Repository analysis must tolerate imperfect repositories.

Possible failures:

```text
invalid GitHub URL
private repository
clone failure
unsupported language
parser failure
large repository
binary files
generated code
malformed source
Git history unavailable
embedding failure
LLM failure
```

One malformed file should not normally destroy an entire repository analysis.

Use partial-success states where possible.

Example:

```text
Analysis completed with warnings.

4,821 files discovered
4,612 files parsed
209 files skipped

Reason:
unsupported/generated/binary files
```

---

# 31. Observability

Future components should expose useful diagnostics.

Track:

```text
ingestion duration
files discovered
files parsed
parser failures
symbols extracted
dependencies extracted
commits processed
embedding count
retrieval latency
LLM latency
ML inference latency
```

The system should make it possible to determine where an analysis failed.

---

# 32. Testing Strategy

Use different testing levels.

### Unit tests

For:

* parsers
* extractors
* metrics
* feature engineering
* graph operations

### Integration tests

For:

```text
repository ingestion
database
API
analysis pipeline
```

### End-to-end tests

Eventually:

```text
GitHub URL
→ ingestion
→ analysis
→ UI
```

Do not attempt complete end-to-end coverage during Phase 0.

---

# 33. Development Principles

### Deterministic before probabilistic

If something can be calculated reliably using code, do not use an LLM.

Examples:

```text
imports
file structure
line counts
Git commits
dependency relationships
graph traversal
```

---

### Evidence before explanation

Retrieve evidence before generating explanations.

---

### Simple before sophisticated

Start with:

```text
PostgreSQL
Tree-sitter
FastAPI
scikit-learn
```

Add infrastructure only when a real requirement exists.

---

### Vertical slices before infrastructure

Prefer a working end-to-end feature over building disconnected infrastructure.

---

### Build for interview depth

Every major subsystem should have a technically defensible reason to exist.

The project should allow discussion of:

```text
AST parsing
graphs
databases
Git analytics
information retrieval
embeddings
RAG
LLM agents
feature engineering
ML
risk modeling
system design
frontend visualization
```

---

# 34. Current Scope

At the beginning of development, ONLY implement:

```text
Phase 0
```

The next implementation target is:

```text
Phase 1
```

Do not implement later phases prematurely.

---

# 35. Definition of Done

A feature is not complete because the UI exists.

A feature is complete when:

```text
Backend logic
+
Data model
+
API
+
Frontend
+
Error handling
+
Tests where appropriate
+
Documentation
```

are sufficiently implemented for that feature's scope.

---

# 36. Commit Convention

Use conventional commits:

```text
feat: add repository ingestion
fix: handle parser failure
refactor: simplify dependency extraction
docs: update architecture
test: add symbol extraction tests
chore: update dependencies
```

Keep commits focused.

---

# 37. AI Agent Context Policy

When an AI agent receives a task:

1. Read this file.
2. Determine the current phase.
3. Read only the files relevant to the task.
4. Do not request or ingest unrelated project context.
5. Implement the smallest correct change.
6. Test the change.
7. Report only relevant modifications and results.

Never repeatedly restate the entire architecture in generated code or prompts.

This document is the source of truth.

---

# 38. Current Objective

The immediate objective is:

> Build the smallest working version of Meredian that can ingest a repository and create a structured representation of its codebase.

Everything else is downstream of that foundation.

```text
GitHub Repository
       ↓
   Ingestion
       ↓
   AST Parsing
       ↓
Structured Repository
       ↓
     Graph
       ↓
   Git History
       ↓
 Semantic Search
       ↓
 Impact Analysis
       ↓
 Risk Prediction
       ↓
 Agentic Intelligence
```

**Build in this order. Do not skip the foundations.**

## Phase 6 - Change Risk Prediction (ML)

**Goal:** Predict the likelihood that a given code change (commit) will be problematic or require subsequent correction, enabling proactive review and testing focus.

**Risk vs Impact vs Uncertainty:**
- **Impact (Phase 5):** The objective blast radius of a change (what will break if the API changes).
- **Risk (Phase 6):** The historical likelihood that a change was problematic based on proxy labels.
- **Uncertainty:** The lack of historical data or test coverage for a specific code path.

**Historical Proxy Label:**

The historical risk label is a **proxy** derived from observable repository history. It is NOT objective ground truth. A commit is labeled as "risky" (1) if it is followed by a corrective commit (e.g., message contains "fix", "revert", "hotfix") within a specific observation window (e.g., 14 days) that modifies at least one of the same files. If the window passes without such a commit, it is labeled safe (0).

**Label Limitations:**
- Not all bugs result in corrective commits with clear terminology.
- Some fixes occur outside the observation window.
- Unrelated fixes in the same file might falsely flag a prior commit.

**Feature Schema:**

Features are extracted deterministically for each commit.
- `files_changed`, `files_added`, `files_modified`, `files_deleted`, `files_renamed`: Numeric counts of changes.
- `prior_change_count`: Total prior changes to the affected files (churn).
- `recent_prior_change_count`: Total prior changes to the affected files within the last 30 days.

**Leakage Prevention:**

To prevent data leakage, features for a commit at time **T** are strictly calculated using information available **at or before** **T**. Future commits, churn, and fixes are strictly excluded from feature extraction and are only used to construct the target label.

**Dataset Limitations:**

Currently, line-level metrics (lines added/deleted), symbol-level historical metrics, and CI/test signals are not reliably tracked in the historical database schema. As a result, they are excluded from the initial feature set. The dataset relies primarily on file-level topology and historical file churn.

---

### Phase 6 Slice 3: Baseline ML Pipeline

  The baseline model is an untuned **Logistic Regression**, trained strictly to predict the historical proxy label.

  **Chronological Evaluation:**

  To evaluate true generalizability and prevent temporal leakage, the dataset undergoes a strict chronological split (80% train / 20% test) sorted by `commit_timestamp`. No future commits or subsequent fixes ever leak into the feature space of an earlier observation.

  **Exact Features:**
1. files_changed
2. files_added
3. files_modified
4. files_deleted
5. files_renamed
6. prior_change_count
7. recent_prior_change_count

  **Model Configuration:**
- `StandardScaler()`
- `LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced")`

  **Baseline Limitations:**
- The model does NOT predict ground-truth software defects. It strictly predicts the likelihood of the historical proxy label (corrective intervention).
- Chronological splitting can lead to severely skewed class distributions in the test set if recent repository history lacks fixes.
- The baseline intentionally omits complex non-linear models (e.g. XGBoost, Random Forest) and textual/semantic features to maintain absolute transparency in the primary Phase 6 rollout.

### Phase 6 Slice 3.5: Baseline Model Audit

  An audit was performed to compare `class_weight=None` against `class_weight="balanced"` on the chronologically split test set.

  **Class-Weight Comparison (Default 0.5 Threshold):**
- `class_weight=None`: Fails to identify the minority class (Recall ~0.003, F1 ~0.006). Accuracy is higher (~0.76) solely due to majority-class dominance. ROC-AUC: 0.636, PR-AUC: 0.295, Brier: 0.177.
- `class_weight="balanced"`: Achieves a much healthier decision boundary (Recall ~0.217, F1 ~0.249). Accuracy drops to ~0.697. ROC-AUC: 0.632, PR-AUC: 0.294, Brier: 0.210.

  **Tradeoffs & Decision:**
- `balanced` trades Brier calibration and raw accuracy for vastly improved recall and F1. This is appropriate because the penalty for a false negative (missing a risky commit) is generally higher than a false positive.
- ROC-AUC and PR-AUC remain functionally identical between configurations, proving that class-weighting does not fundamentally alter the underlying model ranking, only the 0.5 threshold boundary.

  **Repository Distribution Caveat:**

  Because the test set is strictly the most recent 20% of history (chronological), it is naturally dominated by the most actively maintained repositories in that period (e.g., `typer` and `packaging` account for ~85% of test commits). This is structurally correct for time-series evaluation but means aggregate metrics skew toward those specific architectures.

  **Limitations:**
- The model strictly predicts the **historical proxy label**, NOT ground-truth defects.
- PR-AUC (~0.29) and ROC-AUC (~0.63) indicate the 7 purely topological features provide a weak but legitimate baseline signal. Richer semantic and complexity features will be required in subsequent slices to achieve high confidence.

### Phase 6 Slice 3.6: Probability and Calibration Audit

  An audit was performed to determine if the baseline probability outputs (`predict_proba`) can be responsibly exposed via an API.

  **Calibration Findings:**
- `class_weight=None` is roughly calibrated to the dataset base rate (~23% actual vs ~20% mean predicted). However, it clusters almost all predictions below 0.4, crippling its utility as a classifier at the default 0.5 threshold.
- `class_weight="balanced"`, while providing far superior classification metrics (Recall/F1), artificially shifts probabilities upward to balance the classes. The mean predicted probability (0.429) severely overestimates the actual positive rate (0.232). For example, commits assigned a probability in the `[0.5, 0.6)` bin only exhibited a true proxy-positive rate of ~31.4%.

  **Decision & API Terminology:**
- Because `class_weight="balanced"` is selected for classification performance, its raw probabilities are fundamentally uncalibrated.
- **Calibration requires a separate validation-based calibration stage (e.g., Platt scaling or Isotonic Regression on a distinct chronological validation partition) before probability outputs should be interpreted quantitatively.**
- When exposed to the frontend, this output must NOT be called "defect probability" or "bug probability". It will be exposed as the `proxy_risk_score`, reflecting that it is a model estimate associated with the historical proxy label, not ground-truth defects.

### Phase 6 Slice 4: Baseline Risk Prediction Service/API

  A baseline prediction API was created to expose the Logistic Regression model for existing historical commits.

  **API:** `GET /repositories/{repo_id}/risk/predict/{sha}`

  **Key Constraints and Guarantees:**
- **Prediction Target:** Currently operates ONLY on existing historical commits. Hypothetical proposed-change prediction is intentionally deferred.
- **Temporal Isolation:** The prediction uses strictly historical training data. When predicting commit T, the model is trained only on labeled observations strictly prior to T. Neither the target commit nor any future commits are allowed to leak into the training dataset or affect the target feature values.
- **Features:** Identical to the 7 topological baseline features extracted during dataset generation.
- **Output Terminology:** Returns the scalar `proxy_risk_score`. It is strictly associated with the historical corrective-commit proxy label and is explicitly NOT described as a "defect probability" or "bug probability".
- **Calibration Deferred:** The score uses the uncalibrated raw `predict_proba` output from the balanced logistic regression model. Formal Platt-scaling/isotonic calibration is left to a future slice before the score is considered quantitatively calibrated.

### Phase 6 Slice 4.5: Prediction Service Audit

  An audit of the prediction service and dataset was conducted to verify architecture integrity, leakage prevention, and model behavior without adding new functionality.

  **1. Cross-Repository Training Behavior**
- **Verified Behavior:** The current baseline is a **pooled cross-repository model** trained on all historically labeled commits available before the target timestamp, regardless of repository boundaries. Feature extraction remains repository-scoped, but the model itself learns from cross-repository data.

  **2. Temporal Leakage & Determinism**
- **Temporal Isolation Confirmed:** Future commits, labels, and file changes absolutely cannot influence an earlier prediction. The target commit itself is strictly excluded from its own training set.
- **Determinism:** Predictions run multiple times on identical database states yield identical features and scores.

  **3. API & Service Consistency**
- The API endpoint securely routes to the core prediction service and enforces repository scoping (i.e. returning a 404 if the SHA exists in the DB but belongs to another repository).

  **4. Prediction Latency (In-Memory Retraining)**
- Retraining the Logistic Regression model per-request takes roughly:
- ~7ms for older commits (minimal history).
- ~380ms for recent commits (full 7,000-commit history).
- Median time: ~192ms.
- While this latency is strictly a baseline and unoptimized (no caching or background persistence yet), it performs adequately for the current scale without requiring a massive architectural shift to model-binary artifacts.

  **5. Dataset Dominance and Generalization**
- The dataset currently exhibits extreme concentration:
- **Repository 14** (packaging) dominates with 64.7% of total observations and **84.1%** of positive proxy labels.
- **Repository 13** (typer) contributes another 12.7% total and 14.5% of positives.
- The other 12 repositories combined account for barely ~1.4% of the positive labels.
- **Generalization Limitations:** Because of this heavy skew, evaluating true repository-held-out cross-generalization is currently meaningless (leaving out Repository 14 drops the positive class below stability thresholds). The cross-repo pooling is an intentional stop-gap to overcome data scarcity, not a proven generalization capability.

### Phase 6 Slice 5: Historical Risk Feature Expansion

  The historical feature set was expanded beyond the 7 baseline topological features using strictly temporally isolated data.

  **1. Features Implemented**
- `distinct_directories_touched`: Count of unique directories modified by this commit.
- `maximum_files_in_single_directory`: The maximum number of changed files sharing the same directory.
- `average_prior_file_churn`: Across all files changed in this commit, the average number of times they were modified strictly before this commit.
- `maximum_prior_file_churn`: The maximum prior churn of any single file touched by this commit.
- `files_with_high_prior_churn`: Count of files modified in this commit that had > 10 prior modifications.
- `fraction_concentrated_in_most_changed_file`: (maximum_prior_file_churn / sum_prior_file_churn). Measures concentration of historical activity.
- `fraction_of_changed_files_with_high_prior_churn`: (files_with_high_prior_churn / files_changed).
- `repository_prior_commit_count`: Total number of commits in the repository strictly before this commit.

  **2. Features Rejected & Why**
- **Lines added/deleted:** Rejected because line-level change information is not currently stored in `CommitFileChange`. Fabricating it would violate the data model.
- **Dependency features:** Rejected because the `Dependency` table stores only the **current** state of the repository, lacking temporal history. Reconstructing historical dependency graphs is impossible without leakage.
- **Symbol features:** Rejected because the `Symbol` table also stores only current state, introducing massive post-target temporal leakage.
- **Prior positive label counts:** Rejected due to heavy feedback loops and leakage risks (since labels inherently look ahead 14 days, using past labels to predict future ones risks label contamination without strict bounds).

  **3. Temporal Leakage Guarantees**
- Focused tests prove that adding future commits or massive future file changes has absolutely zero impact on the expanded feature vector of a historical target commit. The target commit itself is strictly excluded from its own historical aggregates.

  **4. Baseline Preservation & Prediction Architecture**
- The expanded feature set (15 features) is strictly opt-in (`feature_set="expanded"`). The prediction API and core baseline evaluation still use the standard 7 `BASELINE_FEATURES`.
- **Known Architectural Limitation:** The recent latency audit confirmed that in-memory refitting takes ~80s on average, scaling poorly for recent commits (~210s worst-case). This is explicitly documented but deferred to a future slice dealing with model persistence and serving architecture.

  **Slice 5 Hardening Updates:**
- `maximum_files_in_single_directory` correctly counts **distinct** file paths in the target commit rather than raw `CommitFileChange` rows, preventing duplicate counts for a single path.
- **Rename/Path Semantics Limitation:** Historical file churn is strictly path-based. Rename history is not currently followed through `previous_path`, meaning churn attribution across renames may be incomplete.
- **High-Churn Threshold:** `HIGH_CHURN_THRESHOLD = 10` is an engineering threshold to distinguish highly volatile files, not a statistically validated parameter.
- **Repository Isolation Guarantee:** A new test fixture proves that heavy historical activity in Repository A cannot accidentally contaminate the expanded feature vector of a target commit in Repository B.
- **Idempotency & Finite-Values:** Extracted features are strictly deterministic and mathematically finite (no NaN, PosInf, NegInf).

### Phase 6 Slice 6: Controlled Baseline vs Expanded Evaluation

**Objective:** Measure whether the 8 newly introduced historical features add measurable predictive signal under the same chronological split, using the same `LogisticRegression(class_weight="balanced")` model family and preprocessing.

**1. Identical Dataset & Split**
- **Total Dataset:** 7,001 commits
- **Labeled observations:** 6,953
- **Train size:** 5,562
- **Test size:** 1,391
- **Split timestamp:** `2025-03-13T12:12:55+00:00`
- Both models use the exact same labeled observations and chronological 80/20 split.
- `StandardScaler` is fitted only on the training partition through the model pipeline.
- Baseline uses 7 features; expanded uses 15 features.

**2. Controlled Evaluation**

| Metric | Baseline (7 Features) | Expanded (15 Features) | Difference |
|---|---:|---:|---:|
| Accuracy | 0.6966 | 0.6571 | -0.0395 |
| Precision | 0.2929 | 0.3113 | +0.0184 |
| Recall | 0.2167 | 0.3932 | +0.1765 |
| F1 Score | 0.2491 | 0.3475 | +0.0984 |
| ROC-AUC | 0.6325 | 0.6636 | +0.0312 |
| PR-AUC | 0.2944 | 0.3257 | +0.0313 |
| Brier Score | 0.2099 | 0.1949 | -0.0150 |

These measurements describe performance against the historical corrective-commit proxy label. They are not measurements of real-world defect prediction.

**3. Confusion Matrices**
- **Baseline:** TN 899, FP 169, FN 253, TP 70
- **Expanded:** TN 787, FP 281, FN 196, TP 127

At the existing 0.5 decision threshold, the expanded feature set produced 57 additional true positives and 112 additional false positives on this test split. It also reduced false negatives by 57.

No threshold optimization was performed.

**4. Test-Set Repository Distribution**
- **Repo 13:** 793 observations, positive ratio 0.1589
- **Repo 14:** 402 observations, positive ratio 0.4453
- **Repo 11:** 102 observations, positive ratio 0.0980
- **Repo 10:** 50 observations, positive ratio 0.1400
- **Repo 12:** 27 observations, positive ratio 0.0000
- **Other repositories:** approximately 17 observations combined

The test set remains concentrated in a small number of repositories, so the aggregate metrics should not be interpreted as evidence of broad cross-project generalization.

**5. Coefficient Audit**
- **Baseline largest reported coefficients:** `files_added` (+0.3345), `files_modified` (+0.2884), `files_changed` (+0.2647)
- **Expanded largest reported coefficients by absolute magnitude:** `average_prior_file_churn` (-1.0220), `distinct_directories_touched` (+0.5146), `prior_change_count` (+0.4121)

The expanded feature set contains substantial collinearity, including the previously measured correlation of 0.941 between `maximum_prior_file_churn` and `average_prior_file_churn`. Individual Logistic Regression coefficients therefore must not be interpreted as independent feature importance or causal effects.

**6. Reproducibility**
- Repeated evaluation runs reproduced the same split and metrics.
- The chronological split timestamp remained identical between baseline and expanded evaluations.
- `StandardScaler` was fitted strictly on the training partition.
- The evaluation did not modify production database rows.

**7. Baseline Regression Check**

The 7-feature baseline reproduced the previously established reference behavior:
- Accuracy ≈ `0.696`
- ROC-AUC ≈ `0.632`

Observed values were `0.6966` and `0.6325`, respectively.

**8. Test Results**
- `apps/api/tests/test_ml_evaluation.py`: passed
- Full ML integration suite: 31 tests passed
- Backend tests: passed
- Temporary evaluation script removed
- `git diff --check`: passed

**9. Interpretation and Limitations**

The expanded feature set changes the measured behavior of the same Logistic Regression model on the same chronological test set. The differences are descriptive experimental results, not proof that the expanded features cause better real-world defect detection.

Important limitations remain:
- The target is a historical corrective-commit proxy label, not ground-truth defect data.
- The test set is repository-concentrated.
- The expanded features contain substantial collinearity.
- The current prediction service still performs in-memory model fitting per request; model persistence/caching/serving optimization is deferred.
- No threshold calibration, hyperparameter tuning, feature selection, or new model family was introduced in this slice.
- The reported `proxy_risk_score` must not be represented as a calibrated defect or bug probability.

**Phase 6 Slice 6 status: complete.**

---
