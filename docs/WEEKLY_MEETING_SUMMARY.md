# CastingNuwa — Weekly Meeting & Summary

**Course:** AIE 3905
**Meeting date:** [FILL: e.g. 2026-10-10]
**Time / location:** [FILL: time, room or online link]
**Minutes taken by:** [FILL: name]

> Replace the `[FILL: ...]` fields, then send the short version in Section 8 to the group chat.

---

## 1. Attendees

| Name | Present (Y/N) |
|---|---|
| [FILL: member 1] | [FILL] |
| [FILL: member 2] | [FILL] |
| [FILL: member 3] | [FILL] |
| [FILL: member 4] | [FILL] |
| [FILL: member 5] | [FILL] |

---

## 2. Agenda

1. Confirm the Oct 11 deliverables are complete and runnable.
2. Walk through the current six-step casting workflow.
3. Review the v0.6.1 reliability fixes and test results.
4. Decide how the demo is hosted for this deadline.
5. Assign owners for the next-week real production trial.

---

## 3. Progress this week

- The application is **runnable end-to-end** as a local Gradio web app: role distillation → casting settings → audition tasks → actor observation (text/audio/video) → candidates & human confirmation → crew analysis.
- Independent testing found 14 failed boundary checks; all were fixed in **v0.6.1** and converted into a permanent regression suite (`test_boundary_v06.py`, **20/20 pass**).
- Full regression stays green: end-to-end, app flow, v0.6 flow, crew analyzer (**419/450 = 93%**), vision sampling, and UI smoke tests.
- Key safety behavior verified: empty/insufficient evidence produces "items to verify" instead of a forced middle score; failed real API calls raise an explicit error instead of silently showing fake data.
- The repository is **public** and up to date: https://github.com/xzzmmm/casting
- Submission documents prepared: team journal, project plan, this weekly summary, and an English Quick Start in the README.

---

## 4. Key decisions

1. **Product positioning:** CastingNuwa guides a troupe and organizes evidence; it does not give an automatic acting-quality score or replace the director's decision.
2. **Evidence first:** trait intensity, performance quality and role fit are kept separate; direct observation, self-report and inference are stored separately.
3. **Hosting for Oct 11:** ship the public GitHub repository plus clear local run instructions. GitHub Pages cannot run the Python backend; Hugging Face Spaces hosting is deferred to a later week.
4. **Next milestone:** validate on one real small-scale scene instead of adding more features.

---

## 5. Blockers / risks

- Need to confirm one real short scene and a director contact for the Week 1 trial (Oct 13–19). **[Owner: FILL]**
- Real LLM analysis requires an API key; without it the app stays in clearly labeled demo mode. Decide whether the team shares one small-budget key.
- Full audio/video features are CPU-heavy; MediaPipe face/pose is unavailable on Python 3.13 and degrades to timestamped frame sampling. The text path remains the supported default.

---

## 6. Action items

| # | Task | Owner | Due |
|---|------|---|---|
| 1 | Fill real names and per-member contributions in `docs/JOURNAL.md` | [FILL] | Oct 11 |
| 2 | Confirm the scene/troupe and director for the first real trial | [FILL] | Oct 14 |
| 3 | Prepare script and run role distillation + settings for the trial scene | [FILL] | Oct 16 |
| 4 | Arrange first-round auditions for at least two roles | [FILL] | Oct 19 |
| 5 | Decide on a shared LLM API key/budget for real analysis | [FILL] | Oct 16 |
| 6 | Share the GitHub link with the instructor (GitHub: Fatcat1015) | [FILL] | Oct 11 |
| 7 | Post this weekly summary in the group chat | [FILL] | Oct 11 |

---

## 7. Next meeting

- **Date / time:** [FILL]
- **Focus:** review the first real first-round auditions and prepare coached retests.

---

## 8. Group-chat version (copy and paste)

> **CastingNuwa — Weekly Update (week of Oct 10)**
>
> 1. Our runnable demo is ready: a six-step guided casting web app (role cards → casting settings → audition tasks → actor observation → candidates with evidence → crew plan).
> 2. This week we fixed all 14 boundary issues found in independent testing; the regression suite now passes 20/20 and all other tests stay green (crew analyzer 93%).
> 3. The repo is public and up to date: https://github.com/xzzmmm/casting (run steps are in the README "Quick Start (English)"; it runs without an API key in demo mode).
> 4. Decision for this deadline: submit GitHub + local run instructions; online hosting (Hugging Face Spaces) comes later.
> 5. Next week's goal: run the tool on one real short scene, including first-round auditions for at least two roles.
>
> Action items before next meeting: [FILL: attach owners and due dates from Section 6].
> Please reply with your availability for the next meeting: [FILL: date/time options].
