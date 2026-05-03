# Trace-Grounded Repair — Implementation Plan

A phased plan that takes the project from empty repository to NIER submission with results for the three pre-registered evaluation questions (cross-language transfer, projection ablation, model-scale dependence). Designed for a single PhD student with periodic advisor input. Total estimated effort: **~12 weeks of focused work**, with parallelizable evaluation runs.

The plan is intentionally falsifiable at every phase: each milestone has an acceptance criterion that, if it fails, surfaces a problem early rather than at submission time.

---

## Phase 0 — Project setup (Week 0, ~3 days)

**Goal:** a clean repository, reproducible environment, and a tiny end-to-end smoke test before any real engineering.

### Steps

1. **Repository skeleton.** Create a Python package `tgr/` with submodules `tracer/`, `digest/`, `harness/`, `agent/`, `eval/`. Add `pyproject.toml`, lockfile, and a `tests/` mirror.
2. **Pinned environment.** Python 3.11, locked dependencies via `uv` or `poetry`. Pin the LLM client SDK to a specific version. Pin every analyzed-project's dependencies via per-bug `requirements.txt` snapshots (SWE-bench provides these).
3. **Reproducibility hygiene.** Single `make reproduce` target that, given a bug id, produces a deterministic output (within LLM sampling stochasticity, fixed seed). All experiments write to `runs/<bug_id>/<timestamp>/` with `config.json`, `prompts.jsonl`, `digest.txt`, `patch.diff`, `result.json`.
4. **Smoke test.** Trace one toy bug (e.g. the `rolling_max` example from the paper) end-to-end. Confirm that the tracer fires, a digest is produced, and the loop returns *something*. No quality target—just plumbing.

### Acceptance criterion
`make smoketest` produces a populated `runs/smoketest/` in under 30 seconds.

### Risks
- Underestimating per-bug environment isolation. **Mitigation:** lift SWE-bench's existing Docker images rather than rebuilding.

---

## Phase 1 — Tracer (Weeks 1–2, ~7 working days)

**Goal:** a low-overhead Python tracer that captures the raw signal needed by all three projections, without yet doing any projection-specific work.

### Steps

1. **`sys.settrace` baseline.** Implement `tgr.tracer.LineTracer` that hooks `'call'`, `'line'`, and `'return'` events on a target module's frames. Filter frames by file path so we ignore the test-runner and stdlib.
2. **Snapshot strategy.** On each `'line'` event, snapshot all *local* variables that are scalars, tuples, lists, dicts, sets, dataclasses, and known Python primitives. For larger or opaque objects, record a *fingerprint*: `type`, `len` (if applicable), `repr` truncated to 80 chars, `id`. Never deep-copy unbounded objects.
3. **Branch capture.** Detect conditionals via Python bytecode (`POP_JUMP_IF_*`) using `dis` at module-load time, then record which branch was taken at each `'line'` event whose offset matches a conditional.
4. **Alias capture.** For function-local mutable references, record `id(...)` per binding at each line; emit a delta only when an `id` changes. (Heap-wide aliasing is intentionally out of scope; we only need *local* alias graphs.)
5. **Overhead budget.** Keep the tracer overhead below 10× native test runtime in 90% of cases. Measure on `pytest` micro-benchmarks before declaring done.
6. **Failure injection.** Run on three deliberately broken targets (segfault via `ctypes`, infinite loop, `sys.exit(0)`); confirm the tracer fails gracefully (timeout, sandboxed kill).

### File layout
```
tgr/tracer/
  __init__.py
  line_tracer.py       # sys.settrace wrapper
  snapshot.py          # value -> compact representation
  branch_index.py      # bytecode scan for conditionals
  alias_log.py         # id() tracking for locals
  budget.py            # timeout + memory cap
```

### Acceptance criteria
- Tracer produces a structured `TraceRecord` for the toy bug containing ≥1 entry per executed line, with branch outcomes and final values per local.
- Median overhead ≤ 5× on a 100-bug sample of SWE-bench-Lite Python tests.
- Zero crashes on the failure-injection suite.

### Risks
- **Native code** (e.g. `numpy`, `pandas` C-extensions) is opaque to `sys.settrace`. **Mitigation:** record only at the Python boundary; this is acceptable because the bugs we care about are in *user* Python code.
- **Concurrency** breaks single-threaded tracers. **Mitigation:** restrict pilot to single-threaded tests; document the limitation.

---

## Phase 2 — Three projections (Weeks 3–4, ~8 working days)

**Goal:** three independent, swappable renderers that turn `TraceRecord` into LLM-readable text, each constrained by the C1–C3 design rules from §3 of the paper (locality, bounded inflation, saliency).

### Step 2.1 — Value timeline projector
- For each variable touched in a loop or function body, render the sequence of values it took.
- Elide long sequences with first/middle/last + count: `[1, 5, ..., 8]  (n=128)`.
- Emit as inline `#@` comments on the line of the most recent definition.
- Cap per-line digest length at 120 chars; spill to multiline `#@` blocks above the line if needed.
- **Acceptance:** on the 50-bug pilot set, every digest fits within 1.5× the original file's character count.

### Step 2.2 — Branch ledger projector
- Aggregate per-conditional branch outcomes from the tracer's branch index.
- Render as `#@ branch True at i in {3,4}` immediately under the `if` / `elif` line.
- For loops, render iteration count and last-value-of-loop-variable.
- **Acceptance:** every conditional executed during the failing run has exactly one ledger entry.

### Step 2.3 — Alias summary projector
- Activate only when the failing assertion involves a mutable container or instance.
- Compute a local alias graph: which names in scope point to the same `id`, which mutations were observed through which name.
- Render as a single block of `#@` comments at the function entry: `#@ aliases at fail: cache is window`.
- **Acceptance:** projector activates correctly on the curated alias-driven sub-pilot (10 bugs hand-selected for this projector); zero activations on bugs without mutable state.

### Step 2.4 — Composer
- Single function `compose(source, trace, config) -> augmented_source` that calls all three projectors and inserts their output preserving original line numbers.
- Property test: removing all `#@` comments from the augmented source must reproduce the original file byte-for-byte.

### File layout
```
tgr/digest/
  __init__.py
  values.py            # value timeline
  branches.py          # branch ledger
  aliases.py           # alias summary
  compose.py           # union projector
  shape_check.py       # C1/C2/C3 validators (used in tests)
```

### Risks
- **Inflation overshoot** on long files (e.g. a 2000-line module with one bug). **Mitigation:** localize digest to the function under test plus its direct callers; never digest the whole file.
- **Comment leakage** if the agent's edit accidentally keeps a `#@` line. **Mitigation:** strip `#@` lines before applying any agent patch (already implied by §3 of the paper).

---

## Phase 3 — Agent harness (Week 5, ~5 working days)

**Goal:** wrap an off-the-shelf agent so that swapping `Base` for `Trace` is a single CLI flag.

### Steps

1. **Agent abstraction.** Implement a thin adapter `tgr.agent.Agent` with a single method `propose_patch(repo_state, failing_test) -> Patch`. Two implementations: `BaseAgent` (calls the agent on raw source) and `TraceAgent` (substitutes the augmented source on the agent's first turn only; subsequent turns see the unmodified source).
2. **Loop control.** Cap turns at 5 (matching SWE-agent's default budget). Cap wall time at 5 minutes per bug. On timeout, record `result=timeout` and move on.
3. **Patch application.** Apply the agent's diff to the *original* (un-annotated) tree. Re-run the failing test. Record pass/fail. If fail, re-trace the new failing run and feed the new digest on the next turn.
4. **Determinism scaffolding.** Log full prompts, temperature, sampled completion ids, and exact diff per turn. This is non-negotiable for the rebuttal phase.

### Acceptance criterion
On a 5-bug subset, `tgr-run --agent base --bug X` and `tgr-run --agent trace --bug X` produce identical run-record schemas; only `digest.txt` differs.

### Risks
- **Agent loops that ignore the digest.** Concrete check: log whether the agent's first-turn rationale references any `#@` content. If <50% of trajectories reference it, the digest framing is wrong before the experiment even runs. **Action:** iterate on the prompt template.

---

## Phase 4 — Pilot study (Week 6, ~5 working days)

**Goal:** the 50-bug pilot reported in the paper. This phase exists to confirm the headline result is real *before* committing to the full evaluation.

### Steps

1. **Bug selection.** From SWE-bench Verified, filter to bugs that satisfy: (a) failing assertion involves a mutable container or numerical accumulator (heuristic: AST-scan the failing test for `assertEqual` on `list/dict/numpy`, or for arithmetic equality), (b) failing test runs in <30s, (c) Python only. Sample 50 uniformly.
2. **Pre-registration.** Commit the bug list, agent loop config, and metric definitions to a git tag *before* running. Reviewers will (rightly) ask if the 50 were cherry-picked.
3. **Run both conditions.** Three seeds per bug per condition (300 runs total). Use a job runner (`make pilot SEED=...`) and write to `runs/pilot/`.
4. **Compute metrics.** First-attempt resolution rate, 5-turn resolution rate, median wall time. Bootstrap 95% CIs across the three seeds.
5. **Trajectory audit.** For the 9–15 bugs newly resolved by `Trace`, manually classify whether the agent's rationale references digest content. This is the qualitative claim in §4 of the paper; do *not* skip it.

### Acceptance criterion
- 5-turn resolution lift ≥ +10 absolute points with non-overlapping CIs; otherwise pause and diagnose before scaling up.

### Decision gate
- If the pilot lift is large (≥+15): proceed to Phase 5 confidently.
- If small (+5 to +10): proceed to Phase 5 *and* schedule a digest redesign sprint.
- If absent or negative: do not proceed to full eval. Diagnose first—possible causes: agent ignoring digest (Phase 3 check should have caught this), bug filter too easy, prompt template bug.

### Risks
- **P-hacking the filter.** If the filter is iteratively narrowed to make the lift larger, the result is meaningless. **Mitigation:** filter is frozen at pre-registration. If we change it, we report both the original and revised numbers.

---

## Phase 5 — Full evaluation (Weeks 7–10, ~3 weeks)

**Goal:** answer Q1, Q2, Q3 from §5 of the paper.

### Q1: Cross-benchmark replication
- **Defects4J** (Java). Requires a Java tracer. **Decision:** use an existing JVM tool (e.g. `JDB` scripted, or instrument with ASM) rather than reinventing.
- **BugsInPy** (Python, broader). Direct reuse of the Python tracer.
- **SWE-bench Verified full set** (Python). Same bug filter as the pilot, applied to the full benchmark.
- *Per-benchmark cost estimate:* ~50 GPU-equivalent hours of LLM inference for a single condition + seed combination across all bugs. Plan for ~3000 LLM-runs total across all conditions and seeds.

### Q2: Per-projection ablation
- Conditions: `Trace-V` (value timeline only), `Trace-B` (branch only), `Trace-A` (alias only), `Trace-VB`, `Trace-VA`, `Trace-BA`, `Trace-ALL`.
- Run on the SWE-bench Verified full set and report a 7-row table. Hypothesis: V is necessary, B and A together close the gap on alias-driven and dead-code bugs.

### Q3: Model-scale sweep
- Frontier closed model (one). Strong open-weight model (one). Smaller open-weight (one). Held fixed across all other conditions.
- Hypothesis: smaller models benefit *more* in absolute terms (less internal capacity to simulate execution).

### Q4 (open question, contamination control): scrambled-values control
- Generate digests where structure and format are preserved but values are scrambled (e.g. shuffle the value timeline for each variable). If `Trace-scrambled` produces the same lift as `Trace`, the gain is from format priming, not content. Run on the pilot set first; if signal is real, scale up.

### File layout
```
tgr/eval/
  benchmarks/
    swebench.py
    defects4j.py
    bugsinpy.py
  metrics.py           # resolution rates, CIs
  ablations.py         # condition matrix
  reports/
    generate_tables.py
```

### Acceptance criteria
- Each benchmark has at least one *Trace* condition with statistically significant lift over *Base*.
- Ablation table is fully populated with 95% CIs.
- Scrambled-control lift is significantly smaller than real-trace lift.

### Risks
- **LLM API cost / quota.** Budget ~$3–5k for closed models, plus open-weight inference. **Mitigation:** apply for academic credits early; use open-weight models for ablations to keep closed-model costs to the headline numbers.
- **Defects4J Java tracer slipping.** This is the most likely schedule risk. **Mitigation:** scope a Java tracer prototype in Week 7 day 1; if it's not working by end of Week 8, descope to Q1-Python-only and report as a limitation.

---

## Phase 6 — Analysis & writing (Weeks 11–12, ~10 working days)

**Goal:** turn results into a NIER-quality 4-page paper.

### Steps

1. **Quantitative result tables.** Auto-generate from `runs/`. No hand-edited numbers. Reviewers ask about this.
2. **Qualitative case studies.** Hand-pick 3 bugs that illustrate why the digest matters: one value-timeline bug, one branch bug, one alias bug. Include in the paper as worked examples.
3. **Threats section honesty.** Document every limitation discovered during execution. The Threats section is where reviewers test whether the authors thought about their own work; a generic threats section is a tell.
4. **Independent re-coding.** Have a second annotator re-code the trajectory audit from Phase 4 step 5 *blind* to the condition. Report inter-annotator agreement (Cohen's kappa).
5. **Artifact preparation.** Public repository with a `make reproduce-paper` target that regenerates every table from cached `runs/`. Bug list, prompts, configs all committed.

### Acceptance criteria
- Submission-ready PDF, 4 pages + 2 references, builds cleanly.
- Anonymous artifact repo with a clear README and a 30-minute reproducibility path on a single bug.

---

## Cross-cutting concerns

### Engineering hygiene
- One config file per experiment (`configs/pilot.yaml`, `configs/eval_swebench_full.yaml`). No CLI flags drifting between runs.
- Every run produces a `manifest.json` with git SHA, model id, prompt SHA, dataset SHA. Without these, results are unreproducible.

### Data hygiene
- SWE-bench instances ship with future commits in the repo; the agent must not see them. **Mitigation:** SWE-bench's harness already handles this; verify.

### Cost discipline
- Cache LLM completions keyed on `hash(prompt + model + temperature + seed)`. A single re-run of the eval after a bug fix in the harness should be near-free.

### Schedule slack
- Weeks 1–6 are the critical path; Weeks 7–10 are parallelizable across benchmarks. Reserve at least one week of unplanned slack before submission for the inevitable last-minute issue.

---

## Milestone calendar

| Week | Phase | Deliverable | Pass/fail |
|------|-------|-------------|-----------|
| 0 | Setup | Smoke test green | end-of-week |
| 1–2 | Tracer | TraceRecord on SWE-bench-Lite, ≤5× overhead | week 2 review |
| 3–4 | Projections | Composer produces validated digests on 100 bugs | week 4 review |
| 5 | Harness | Single-flag swap between Base and Trace | end-of-week |
| 6 | Pilot | 50-bug pilot, decision gate | **GO/NO-GO** |
| 7–8 | Eval Q1 | Cross-benchmark numbers (Python at minimum) | week 8 review |
| 9 | Eval Q2 | Ablation table | end-of-week |
| 10 | Eval Q3 + Q4 | Model-scale sweep + scrambled control | end-of-week |
| 11 | Analysis | Tables, case studies, threats | end-of-week |
| 12 | Writing | Submission-ready PDF + artifact | submission |

---

## What this plan deliberately does *not* do

- **No model fine-tuning.** The whole point of NIER is to demonstrate the digest works with off-the-shelf agents. A fine-tuned ablation is fair game for the follow-up full paper.
- **No multi-language tracer beyond Defects4J.** JavaScript, C, Rust are out of scope for the NIER submission; they belong in the follow-up.
- **No production tooling.** This is a research artifact, not a deployable system. We do not build a VS Code extension, a CI integration, or a robust multi-tenant service. The reviewer cares about the result, not the polish.
- **No fancy ML on the digest.** A learned digest renderer is a tempting follow-up, but the NIER claim is that *even a hand-designed digest* yields a large lift. Hand-designed first, learned second.

The discipline of saying "no" to these is what keeps a 12-week project from becoming a 12-month one.
