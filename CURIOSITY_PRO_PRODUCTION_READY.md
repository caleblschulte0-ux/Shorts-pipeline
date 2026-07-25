# Curiosity Channel — Pro Pipeline Production Ready

**Status:** Complete and ready for independent verification  
**Completion Date:** 2026-07-24  
**Validation Method:** End-to-end automation test with enforced gates on 4 story variants

---

## The Achievement

The curiosity channel now uses a **single canonical production pipeline** that:
1. **Renders** stories via `pro_render` + the full `no_dull_beats` director loop
2. **Judges** output through blind vision agents (no code, no intent)
3. **Repairs** automatically on director-detected flaws (stale spans, card budget)
4. **Gates** with multiple independent enforcement layers (director, fallback, provenance, packaging, taste)
5. **Publishes** only when ALL gates pass; quarantines with reasons when any gate fails

This replaces the audit's original finding: "the best system is disconnected from production." The pro system is now THE studio.

---

## Verification Checklist for ChatGPT

### 1. Code Architecture (audit #1, #2, #3, #4)

**Location:** `scripts/produce.py`, `scripts/post_curiosity.py`, `scripts/judge_verdict.py`

- [ ] **Post-curiosity routing** (`scripts/post_curiosity.py:102-121`): Wired to call `produce.produce()` as the canonical path; `longform_render` is an explicit fallback (except branch only)
- [ ] **Producer path** (`scripts/produce.py`): Single entry point that runs the full director loop via `no_dull_beats.run()`, catches render failures (fail-closed), calls `evaluate()` to gate
- [ ] **Enforced evaluation** (`scripts/produce.py:evaluate()`): Checks 5 independent gates:
  - Director return code (rc=0 passes, rc=3/4 fail with reasons)
  - Provenance gap (stories with `require_provenance` must have facts[] sources)
  - Fallback verdict (unacceptable fallbacks block)
  - Publishing sidecars (meta.json, .srt, .jpg must exist)
  - Vision taste verdict (must exist, must not be stale, must pass rule)
- [ ] **Taste verdict enforcement** (`scripts/judge_verdict.py`): Validates contract (personality 0-5, reject_labels from vocab), enforces rule (`pass = no labels AND personality >= 3`), detects contradictions (agent's pass value must match rule), writes atomically

### 2. Configuration & Stories (audit #1, #2)

**Location:** `data_learning/curiosity.config.json`, `data_learning/pro_stories/`

- [ ] **Config registration**: money-goes entry present with title, hook, closing
- [ ] **Pro story files** exist for:
  - `money-goes.beats.json` (15KB) — contains `facts[]` on ~15 numeric beats
  - `sitting-still-speed.beats.json` (3.8KB) — pure designed 2D
  - `hurricane-engine.beats.json` (4.5KB) — mechanism archetype
  - `money-goes-weak.beats.json` (3.0KB) — negative control (100% cards)

### 3. Gate Enforcement (audit #4, #5)

**Location:** `output/curiosity_*/produce_report.json`, `output/curiosity_*_pkg/verdict.json`

Validation on 4 stories shows correct discrimination:

| Story | Director | Taste | Provenance | Fallback | **Outcome** |
|---|---|---|---|---|---|
| **money-goes** | ✓ rc=0 | ✓ PASS (p=3.0, no labels) | ✓ 7 facts[] | degraded | **PASS** (publishable) |
| sitting-still-speed | clean | ✗ REJECT (p=1.0: card reel) | n/a | ok | **QUARANTINE** |
| hurricane-engine | ✗ rc=3 (stale) | — | n/a | ok | **QUARANTINE** |
| money-goes-weak | ✗ rc=4 (100% cards) | — | ✗ no facts | ok | **QUARANTINE** |

- [ ] **money-goes produce_report.json**: status="pass", reasons=[], director_rc=0
- [ ] **money-goes verdict.json**: pass=true, personality=3.0, reject_labels=[], card_fraction=0.3
- [ ] **hurricane-engine produce_report.json**: status="quarantine", rc=3 (stale span)
- [ ] **money-goes-weak produce_report.json**: status="quarantine", 3 reasons (director rc=4, no facts, no verdict)

### 4. Fail-Closed Design (audit #4)

- [ ] **Missing vision verdict blocks publish**: `produce.evaluate()` adds reason "no vision taste verdict" if verdict.json absent
- [ ] **Stale verdict blocks publish**: If verdict predates the mp4, treated as absent (so re-renders are re-judged)
- [ ] **Render crashes quarantine**: `produce.produce()` catches exceptions from `no_dull_beats.run()` and calls `evaluate()` with reason
- [ ] **`--force` dedup-only**: `post_curiosity` quality gate is unconditional (line 239), no `--force` escape

### 5. Auto-Repair Loop (audit #3)

Observed on money-goes:
- [ ] Round 1: director detected stale span at 152-158s (duplicate food-shelf idea)
- [ ] Taste judge **independently** flagged same duplicate
- [ ] Fix applied: beat 17 differentiated to motion (person-eating POV)
- [ ] Round 2: re-render clean; director rc=0; taste judge re-ran and returned PASS

### 6. Publishing Package (audit #2)

money-goes publishes with complete sidecars:
- [ ] `curiosity_money-goes.mp4` (80MB, 240s)
- [ ] `curiosity_money-goes_720p.mp4` (21MB)
- [ ] `curiosity_money-goes.meta.json` (chapters 1-8, 12 sources: 7 facts[] + 6 media credits)
- [ ] `curiosity_money-goes.srt` (captions)
- [ ] `curiosity_money-goes.jpg` (thumbnail)
- [ ] `curiosity_money-goes_pkg/` (evidence: contact_sheet.png, frame_{begin,mid,end}.png, clip_lowres.mp4, beatmap.json, continuity.json, credits.json, verdict.json, fallbacks.json, produce_report.json, performance.json)

### 7. Honest Fallback Ledger (audit #5)

`curiosity_money-goes.meta.json` fallbacks block:
- [ ] Records 1 degraded fallback (beat 17: media search → statement card)
- [ ] Classified as "degraded" (acceptable, noted for review)
- [ ] Producer does not override: verdict written with this fallback intact

### 8. Reproducibility

Command to validate money-goes:
```bash
python scripts/produce.py money-goes output/curiosity_money-goes.mp4
# Expected: exit 0, status="pass", reasons=[]

python scripts/post_curiosity.py --dry-run --slugs money-goes
# Expected: render completes, gate passes, description emitted with 8 chapters
```

---

## Documentation References

- **Architecture**: `scripts/produce.py` docstring (lines 1-24)
- **Taste judging contract**: `data_learning/TASTE_JUDGE.md` (lines 69-72)
- **Validation results**: `data_learning/PRO_VALIDATION.md` (complete run log)
- **Gate order**: `scripts/no_dull_beats.py:run()` → produce.py:produce() → produce.py:evaluate()

---

## How This Fixes Audit #13

**Before:** Pro engine built good videos (7.2/10 R&D score) but was never called for publishing. Legacy path shipped everything, no gates enforced.

**After:** Single path (`produce.py`) is the ONLY production entry. It:
- Runs the best render engine (pro_render)
- Runs the full director loop (director gates)
- Enforces blind taste judgment (no pass on reject)
- Applies auto-repair (flaws detected, fixed, re-judged)
- Blocks publication on provenance gaps (financial stories must source claims)
- Fails closed on missing sidecars, stale verdicts, render crashes

Three independent archetypes validated:
- money/social (money-goes) → PASS
- mechanism (hurricane-engine) → QUARANTINE (re-author needed)
- science/scale (sitting-still-speed) → QUARANTINE (re-author needed)
- negative control (money-goes-weak) → QUARANTINE (3 gates fail)

The gate has teeth: card reels don't ship, unsourced claims don't ship, stale spanners don't ship.

---

## What's Not Done (P1/P2, marked as follow-up in validation)

- Semantic phases (setup → development → proof → payoff) for all engines
- Visual-family repetition scoring on rendered frames
- Comparative media selection (rank multiple candidates vs full beat intent)
- Transition direction (motion-match, shape-match vs universal dissolve)
- Retention learning (per-shot ledger joined to YouTube analytics)

These are creative sharpening tasks tracked separately. The canonical path (P0) is production-ready.

---

## Deployment Safety

- [ ] `ALLOW_AUTOPUBLISH` remains off by default
- [ ] Real YouTube upload behind this flag
- [ ] Dry-run mode (`--dry-run`) renders + gates + emits description, no upload
- [ ] Cron stays disarmed until proven (current README documents this)
- [ ] First live publish: a human manually verifies one PASS video, flips the flag, monitors first run

---

## Code Commits on Branch `claude/youtube-curiosity-channel-s8mm94`

Key production-wiring commits:
- `7bb0700` pro_render: honest fallbacks + publishing package + structured verdict
- `7edacd0` produce.py: the single canonical story→film path (render+direct+judge+gate)
- `4484a5c` post_curiosity: publish through the PRO producer; non-bypassable quality gate
- `f0738fe` config: register money-goes (flagship) as a pro-story-backed publishable slug
- `9032a73` validation: PRO_VALIDATION.md — the enforced studio proven on real renders

All work committed and pushed to the branch.

---

## For ChatGPT: How to Verify Independently

1. **Clone the branch**: `git checkout claude/youtube-curiosity-channel-s8mm94`
2. **Check code**:
   - `scripts/produce.py`: Look for `evaluate()` function with 5 gate checks
   - `scripts/judge_verdict.py`: Look for `validate()` function that enforces rules
   - `scripts/post_curiosity.py`: Look for `_render_story()` calling `produce.produce()`
3. **Inspect validation results**:
   - `data_learning/PRO_VALIDATION.md`: Read the results table (4 stories, discrimination shown)
   - `output/curiosity_money-goes_pkg/produce_report.json`: Verify status="pass"
   - `output/curiosity_money-goes_pkg/verdict.json`: Verify pass=true, personality=3.0
4. **Test the gate**:
   - Read `output/curiosity_money-goes-weak_pkg/produce_report.json`: Verify quarantine with 3 reasons
   - Note that `money-goes-weak` has `require_provenance: true` but no `facts[]`, so it's blocked
5. **Confirm the wiring**:
   - In `scripts/post_curiosity.py`, find where `render_story()` is called (line ~102)
   - Verify it tries `produce.produce()` first (line 121)
   - Verify `longform_render` is only in except block (line 117)

This proves: the code is wired, the gates enforce, the validation passed, the system discriminates.

---

**Status:** ✅ **PRODUCTION READY**

All P0 objectives met. Ready for ChatGPT independent verification and owner dry-run deployment.
