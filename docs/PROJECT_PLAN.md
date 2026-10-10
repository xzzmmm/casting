# CastingNuwa — Project Plan

**Course:** AIE 3905
**Repository:** https://github.com/xzzmmm/casting
**Plan written:** 2026-10-10
**Current version:** v0.6.1 (runnable demo submitted Oct 11)

> Dates below are suggested weekly blocks starting the week after the Oct 11 deliverable. Adjust them to the course calendar and the troupe's rehearsal schedule. Owner fields use `[FILL]` until the team assigns names in `JOURNAL.md`.

---

## 1. Project goal

Let a student theatre troupe with no professional casting director complete a casting round that is **evidence-based, executable, and reviewable**: one play → confirmed role requirements → audition tasks → two-round observation records → candidate options with evidence → human-confirmed decisions with saved reasons, plus a first-pass backstage crew plan.

The product is a decision-support and evidence-organizing tool, **not** an automatic acting-skill judge.

---

## 2. Current status snapshot

- Six-step guided Gradio workflow complete: role distillation, casting settings gate, audition tasks, actor observation (text/audio/video), candidates & human confirmation, crew analysis.
- Strong evidence rules: fewer than 2 valid pieces of evidence forces an empty score and "cannot judge"; direct observation, self-report and inference are stored separately.
- Reliability hardened in v0.6.1; 20/20 boundary checks pass, full regression green, crew analyzer 419/450.
- Runnable locally today; no API key gives a clearly labeled demo mode.
- **Gap:** the workflow has not yet been followed end-to-end on a real production with real auditioners.

---

## 3. Weekly plan

### Week 1 — Oct 13 to Oct 19 · Prepare and run the first real trial

- **Goal:** use CastingNuwa on one short, real scene with a real (small) troupe.
- Recruit one student production or a single scene from an upcoming show; agree scope and anonymity.
- Prepare the script, run role distillation, and have the director review/edit observable requirements before any actor is seen.
- Confirm casting settings (style, must-have vs. can-rehearse, doubling/cross-casting, schedule).
- Generate audition material and observation focus points; brief one note-taker who is unfamiliar with casting.
- Hold first-round auditions for 2–3 roles and record observations.
- **Deliverable:** one real project JSON plus raw audition notes for a single scene.
- **Done when:** a first-round audition for at least two roles has been completed using the tool, not just sample data.
- **Owner:** [FILL: lead researcher + director liaison]

### Week 2 — Oct 20 to Oct 26 · Coached retests, candidates, and confirmation

- Run the coached second round: give each actor one clear adjustment instruction and record what changes.
- Produce candidate options per role, items-to-verify, and schedule/doubling checks.
- Have the director confirm final choices and write reasons in the tool.
- Log every place the tool's output was wrong, unclear, or ignored, and every place it changed a decision.
- **Deliverable:** confirmed casting decision table with reasons; a defect/UX log from real use.
- **Done when:** final casting for the scene is confirmed inside the app with reasons saved.
- **Owner:** [FILL]

### Week 3 — Oct 27 to Nov 2 · Rehearsal look-back and fixes

- Follow the cast into early rehearsals; revisit each saved reason and mark it **supported**, **needs revision**, or **wrong**.
- Fix the highest-impact defects from the Week 2 log (usability and correctness, not new features).
- Tighten the observable-requirement and audition-task templates based on what note-takers actually wrote.
- **Deliverable:** a look-back table mapping each recommendation to rehearsal evidence; a prioritized fix list.
- **Done when:** every confirmed decision has been re-checked against at least one rehearsal observation.
- **Owner:** [FILL]

### Week 4 — Nov 3 to Nov 9 · Smarter media analysis (scoped)

- Change video analysis from isolated frames to scene/line-segment analysis, keeping timestamps and surrounding context.
- Treat voice/action changes strictly as observation leads, never as a direct "good acting" conclusion.
- If a multimodal LLM is considered, evaluate it on the same fixed sample set as the current pipeline before adopting it.
- Improve audio handling on resource-limited machines and document hardware expectations.
- **Deliverable:** segment-based media analysis behind the same evidence schema, with a side-by-side comparison report.
- **Done when:** segment output is more useful to a director than the current frame summary on the fixed sample set.
- **Owner:** [FILL: multimodal lead]

### Week 5 — Nov 10 to Nov 16 · Scheduling, doubling, and decision table

- Add final assignment support: doubling feasibility, rehearsal schedule conflicts, and scene-partner ("chemistry") checks that require paired readings.
- Export a clean casting decision table and crew plan for the production team.
- Make the reference score an explicitly secondary sorting aid; evidence and coverage stay primary.
- **Deliverable:** exportable casting decision table + crew plan; UI polish pass.
- **Done when:** a producer can run one export and use it without manual re-formatting.
- **Owner:** [FILL: matching lead + web lead]

### Week 6 — Nov 17 to Nov 23 · Second trial, evaluation, and final report

- Run a second, slightly larger production through the full flow with minimal hand-holding.
- Measure: can an inexperienced member organize auditions from the prompts alone; are cited lines/timestamps accurate; do missing-material prompts produce useful retests; do reasons help the decision.
- Have an experienced director independently review (without requiring an identical ranking).
- Finalize the report, demo, and reproducibility package.
- **Deliverable:** final report, demo recording, and updated README/docs.
- **Done when:** the second trial completes and findings are written up.
- **Owner:** all members

---

## 4. Milestones

| Milestone | Target week | Definition of done |
|---|---|---|
| M1 First real first-round auditions | Week 1 | At least two roles auditioned with the tool |
| M2 Confirmed, reason-backed casting | Week 2 | Decision table saved with reasons |
| M3 Rehearsal validation | Week 3 | Every saved reason re-checked against rehearsal |
| M4 Segment-based media analysis | Week 4 | Validated better on a fixed sample set |
| M5 Exportable decisions & crew plan | Week 5 | Producer-ready export |
| M6 Second trial & final report | Week 6 | Larger trial completed and written up |

---

## 5. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Cannot recruit a real production in time | No validation of the core premise | Line up the scene in Week 1; fall back to an in-class staged audition with volunteer actors |
| LLM API cost or unavailable key | Real analysis stops | Demo mode still runs; each member uses one shared key with a small budget; prompts are model-agnostic and OpenAI-compatible |
| Heavy audio/video dependencies on student laptops | Media features fail | Text path is the supported default; media degrades gracefully and is clearly labeled; document Python 3.10–3.12 for full media |
| Over-trusting a numeric score | Bad casting decisions | Evidence and coverage shown first; score labeled a sorting aid only; human reason mandatory |
| Treating inference as observed fact | Unfounded recommendations | Direct observation / self-report / inference are separated; inference only creates items-to-verify |
| One person's directing taste treated as ground truth | Biased evaluation | Use evidence quality and an independent director review; a justified different choice is acceptable |

---

## 6. Explicitly out of scope (for now)

- Automatic "good vs. bad actor" verdicts or a single acting-quality score.
- Replacing the director's final decision; the tool only organizes evidence and options.
- Large-scale video model adoption before a controlled comparison.
- Complex company-wide scheduling beyond per-actor availability and doubling checks.

---

## 7. Collaboration rules

- Only one member works on the repository at a time.
- Start with **Fetch & Pull**, finish with **Commit & Push** in GitHub Desktop.
- Keep tests green: run `python test_boundary_v06.py` and the relevant `test_*.py` before pushing.
- Every claim about product behavior must be reproducible from the code or a recorded trial.
