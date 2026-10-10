# CastingNuwa — Team Journal

**Course:** AIE 3905 · Project CastingNuwa (选角女娲)
**Repository:** https://github.com/xzzmmm/casting
**Last updated:** 2026-10-10

> **Before submitting, replace every `[FILL: ...]` placeholder with the real information, then delete this note.**
> All technical work items below are traced to real commits and files. Names are left as placeholders because the repository was pushed from a single GitHub account; assign each row to the teammate who actually did the work. Add or remove member rows to match your team size.

---

## 1. Team members

| # | Name | GitHub username | Primary role area |
|---|------|-----------------|-------------------|
| 1 | [FILL: name] | [FILL: username] | [FILL: e.g. user research & product] |
| 2 | [FILL: name] | [FILL: username] | [FILL: e.g. prompts & role/actor logic] |
| 3 | [FILL: name] | [FILL: username] | [FILL: e.g. matching engine & data models] |
| 4 | [FILL: name] | [FILL: username] | [FILL: e.g. multimodal & web app] |
| 5 | [FILL: name] | [FILL: username] | [FILL: e.g. testing & documentation] |

Suggested role areas (merge them to fit your team size):

- **User research & product direction** — interviews, problem definition, workflow design.
- **Prompt & LLM logic** — role distillation, actor profiling, audition task prompts, structured JSON rules.
- **Matching & data models** — evidence comparison, candidate classification, production crew analysis, serialization.
- **Multimodal & web** — audio/video pipelines, Gradio UI, sessions, project save/load, deployment.
- **QA & documentation** — test suites, boundary tests, README, journal and plan.

---

## 2. How we work

- Only one member works on the repository at a time to avoid conflicts.
- Before starting: **Fetch & Pull** in GitHub Desktop.
- After finishing: **Commit & Push** in GitHub Desktop with a descriptive message.
- Every product decision is tied to either user interview evidence or a reproducible test, not personal opinion.

---

## 3. Detailed work log by phase

Status legend: Owner column uses `[M1] ... [M5]` placeholders for the five members above.

### Phase 0 — Problem discovery & user research (Week 1, early–mid Sep)

| Work item | What was done | Evidence | Owner |
|---|---|---|---|
| Interview protocol | Wrote a structured interview protocol with 5 behavior-based questions (past, specific events), follow-up probes, a things-to-see evidence list, 18-minute timing plan, and ethics/consent checklist. | Interview Protocol deliverable (Week 2, "What Users Don't Say") | [FILL] |
| User interviews | Interviewed student-theatre directors and a producer / stage manager / HR contact about casting and crew allocation; collected casting notices, sign-up forms, audition scoring sheets, scheduling tables and lighting/sound requirement lists. | Interview notes & collected artefacts | [FILL] |
| Needs record card | Designed a requirement-recording card template to capture role and backstage needs during interviews. | Research artefact | [FILL] |
| Problem definition | Identified the information gap between script/stage directions and actual casting & crew decisions: long casting cycles, inefficient first-pass screening, ad-hoc backstage staffing, and decisions that cannot be reviewed afterwards. | docs/项目方案.md | [FILL] |

### Phase 1 — First working prototype, v0.3 (Sep 13)

| Work item | What was done | Evidence | Owner |
|---|---|---|---|
| Initial application | Built the first AI drama casting assistant with multimodal actor profiling and quantitative trait matching. | Commit `Initial commit` (Sep 13) | [FILL] |
| Repository setup | Created the GitHub repository, README baseline and project structure. | Commit `Merge remote repository, use local README` (Sep 13) | [FILL] |

### Phase 2 — Production crew analysis (Sep 14)

| Work item | What was done | Evidence | Owner |
|---|---|---|---|
| Crew requirement module | Added automatic analysis of lighting, sound, stage design, costume, props and makeup needs from the script, each conclusion tied to script evidence. | `src/crew_analyzer.py`, `src/crew_prompts.py` | [FILL] |
| Heuristic rules engine | Built a deterministic rule-based analysis engine so crew estimates still work without an LLM call. | Commit `feat: 制作团队分析新增启发式规则分析引擎` | [FILL] |
| Crew test suite | Added a 450-case test suite for the crew analyzer. | `test_crew_analyzer.py`; commits Sep 14 | [FILL] |

### Phase 3 — Product re-direction, v0.5 (Sep 19)

| Work item | What was done | Evidence | Owner |
|---|---|---|---|
| Core re-design | Changed the product from "upload material, AI gives a score and ranking" to "guide a student troupe through an evidence-based, reviewable casting process." | Commit `v0.5 重构` (Sep 19) | [FILL] |
| Observation records | Replaced personality judgments with structured records: what happened, possible meaning (with alternative explanations), evidence type, and how to verify next. | `src/actor_models.py`, `src/actor_profiler.py` | [FILL] |
| Candidate classification | Replaced single-score ranking with three categories — priority audition, needs more audition, explicit limit — plus evidence comparison. | `src/matching_engine.py` | [FILL] |
| Concept separation | Explicitly separated trait intensity, performance quality and role fit, so a mid-range score is never read as "average acting skill." | README "三条不能混淆的界线" | [FILL] |

### Phase 4 — Guided workflow, v0.6 (Sep 19)

| Work item | What was done | Evidence | Owner |
|---|---|---|---|
| Six-step web flow | Organized the Gradio app into six guided tabs: role distillation, casting settings, audition tasks, actor observation, candidates & confirmation, crew analysis. | `app.py` | [FILL] |
| Observable requirements | Translated personality labels into observable performance requirements (e.g. using pauses, averted gaze and limited movement to show hidden emotion). | `src/models.py`, `src/role_distiller.py` | [FILL] |
| Settings gate | Added a confirmation checkpoint for performance style, must-have vs. can-rehearse requirements, cross-casting/doubling and schedule constraints; matching is blocked until confirmed. | `app.py`, `src/models.py` | [FILL] |
| Two-round audition | Generated unified audition material, 2–3 observation focus points, one adjustment instruction, and a retest task; recorded coached second-round responses. | `src/audition_designer.py`, `src/audition_prompts.py` | [FILL] |
| Verification items | When evidence is insufficient, the system produces items-to-verify instead of forcing a middle score. | `src/actor_models.py`, `src/actor_profiler.py` | [FILL] |
| Human confirmation | Required a human to confirm the final actor and save the reason; added doubling, schedule and scene-chemistry checks. | `src/matching_engine.py`, `app.py` | [FILL] |
| Session isolation & save/load | Scoped all state to the browser session; added whole-project JSON save/load. | `app.py` | [FILL] |
| Full-span video sampling | Switched video analysis to uniform sampling across the whole clip with per-frame timestamps, instead of only reading the opening. | `src/vision_processor.py` | [FILL] |

### Phase 5 — Reliability hardening, v0.6.1 (Sep 22)

An independent tester ran the existing tests plus 20 targeted boundary checks (6 passed, 14 failed). All failures were fixed and converted into a permanent regression suite.

| Work item (issue) | What was done | Evidence | Owner |
|---|---|---|---|
| P1-1 Media callback index error | Unified the success/failure return shape for audio and video callbacks; a successful analysis now displays correctly and adds the actor exactly once. | `app.py` `_append_media_profile` | [FILL] |
| P1-2 Text entry overwrote roster | Changed text actor entry to upsert by actor name so adding one person or a retest never wipes the existing roster. | `app.py` `profile_actors` | [FILL] |
| P1-3 Same-second save collision | Added a short UUID to save/export filenames and atomic temp-file replacement, so two sessions saving in the same second never overwrite each other. | `app.py` save/export | [FILL] |
| P1-4 Evidence rules bypassed | Counted only real, de-duplicated, locatable evidence; rejected empty profiles as failed; validated candidate category, score range and actor identity; demoted evidence-free "priority" proposals. | `src/models.py`, `src/actor_models.py`, `src/matching_engine.py`, `src/multimodal_analyzer.py` | [FILL] |
| P1-5 Inference treated as observation | Restricted supporting evidence to direct observation (not self-report); inference and self-report only generate tentative leads / items-to-verify. | `src/matching_engine.py` | [FILL] |
| P1-6 Stale results after settings change | Material setting changes now invalidate prior candidates, confirmations and audition tasks; single-role matching enforces the same settings-confirmed gate as full matching. | `app.py` | [FILL] |
| P2 batch | Atomic project import (bad files cannot half-overwrite the current project); automatic `.env` loading; explicit error when an API key is set but the SDK is missing; completed multimodal dependencies; mandatory confirmation reason; rewrote the outdated end-to-end test. | `app.py`, `src/llm_client.py`, `requirements*.txt`, `test_e2e.py` | [FILL] |
| Boundary regression | Adapted the tester's 20 checks into a permanent suite; all 20 pass. | `test_boundary_v06.py` (20/20) | [FILL] |

### Phase 6 — Testing & submission preparation (Sep 23 – Oct 10)

| Work item | What was done | Evidence | Owner |
|---|---|---|---|
| Two-round audition test | Added/updated tests for the two-round audition tasks and packaged a demo archive. | Commit `c48ddc8` (Sep 29) | [FILL] |
| Full regression | Kept all suites green: end-to-end, app flow, v0.6 flow, crew analyzer (419/450 = 93%), vision sampling, UI smoke, 20 boundary checks. | `test_*.py`, `smoke_ui.py` | [FILL] |
| Graceful degradation | Verified that when MediaPipe is unavailable (e.g. Python 3.13), vision analysis degrades to frame sampling with a clear label instead of failing silently. | `test_vision_sampling.py` | [FILL] |
| Deployment evaluation | Compared GitHub Pages (static-only, cannot run Python), Hugging Face Spaces and Render; chose to ship the GitHub repository plus local run instructions for this deadline. | README, team decision | [FILL] |
| Submission documents | Produced this journal, the project plan and the weekly meeting summary; added an English Quick Start to the README. | `docs/JOURNAL.md`, `docs/PROJECT_PLAN.md`, `docs/WEEKLY_MEETING_SUMMARY.md`, `README.md` | [FILL] |

---

## 4. Per-member contribution summary

> Duplicate the block below once per member and fill it in. Keep claims consistent with the work log above.

### [FILL: Member name] (`[FILL: GitHub]`)

- **Role:** [FILL]
- **Main contributions:**
  - [FILL: concrete item, linked to a phase / file / commit]
  - [FILL: concrete item]
  - [FILL: concrete item]
- **Hours spent (optional):** [FILL]

---

## 5. Testing & quality evidence

| Test | What it covers | Result |
|---|---|---|
| `test_boundary_v06.py` | 20 high-risk boundary cases from the independent test report | 20/20 pass |
| `test_e2e.py` | End-to-end six-step flow, aggregated per role, confirmation reason | pass |
| `test_app_flow.py` | Real app flow; candidate classification baseline (priority vs. needs-more) | pass |
| `test_v06_flow.py` | Six-step flow, settings gate, save/load round-trip, human confirmation | pass |
| `test_crew_analyzer.py` | 450 crew-analysis cases | 419/450 = 93% |
| `test_vision_sampling.py` | Full-span frame sampling and timestamps; MediaPipe degradation | pass |
| `smoke_ui.py` | Gradio UI builds without errors | pass |

---

## 6. Known limitations (stated honestly)

- Without an `LLM_API_KEY` the app runs in clearly labeled demo mode; demo output must not be used for real casting.
- Audio/video analysis uses local models and is CPU-intensive; on Python 3.13 the MediaPipe face/pose API is unavailable, so vision degrades to timestamped frame sampling.
- The matching logic has been validated for workflow correctness, not against a large set of professional casting outcomes. It supports decisions rather than judging acting skill.
- The next required step is a real small-scale production trial (Phase 5 in the project plan).
