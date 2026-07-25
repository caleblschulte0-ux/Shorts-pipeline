# Emotional Expression System — Evolution Roadmap

## Current State

The expression system is implemented, wired, and MEASURED (2026-07-24):

### What's Implemented
- **7 emotions** with clamped pose-delta mappings (joy, shock, resignation,
  frustration, burden, exhaustion, relief) — `data_learning/expression.py`
- **6 pose parameters** with safe bounds (arms_up, stride, lean, head_drop,
  body_sway, gesture_speed); the pictogram (`_stand`) realizes arms_up,
  stride, lean and head_drop on-figure
- **Windowed linear interpolation** of emotion strength (start/end/intensity)
- **Both config forms**: structured `{"expression": {...}}` (production) and
  legacy `{"express": true}` (maps to each scene's default emotion)
- **Six scenes consume the structured path** via a shared `_expr_delta()`
  helper: paycheck, tax, rent, gas, money, treadmill — no scene invents its
  own emotion math beyond documented overrides (paycheck's joy fade-out)
- **The flagship arc is authored in the beats**: joy -> shock -> frustration
  -> resignation -> burden -> exhaustion -> resignation

### Measured Evidence (not claims)
- Frame-diff proof: baseline-vs-expression sweeps **1,400-5,600 strongly
  changed pixels** per scene at beat end (threshold 600; identical renders
  measure exactly 0) — `scripts/verify_expressions.py`
- Same-scene x10 loop: **flat** (0.95x first->last), RSS +0.1MB, fd +0 —
  the render loop does not degrade; the historical slowdown was the external
  media path, now separately timed per shot (`asset_resolution` in
  `performance.json`) — `scripts/perf_experiments.py`
- Assembly (dissolve_join): 0.89x realtime — not a bottleneck
- CI: `.github/workflows/expression-tests.yml` runs the gates, the measured
  visual proof, and the leak check on every relevant change

---

## Phase 2.1 — Persistent Character State (Next Generation)

**Goal:** Enable character emotional state to carry across scenes, allowing the pictogram to "learn" and evolve throughout the video.

### Current Limitation
Each scene is stateless — emotions are isolated per-beat and reset between scenes. This creates missed opportunities for narrative continuity:
- A character shocked by taxes doesn't carry that shock into the housing discussion
- No sense of cumulative stress or growing resignation
- Each scene resets the emotional baseline

### Proposed Architecture

```python
class CharacterState:
    """Persistent emotional and physical state across scenes."""
    
    # Current state
    current_emotion: Emotion = "resignation"
    stress_level: float = 0.0  # [0, 1] cumulative stress
    energy_level: float = 1.0  # [0, 1] fatigue from activity
    confidence: float = 0.5    # [0, 1] belief in future outcomes
    
    # History (for transition curves)
    emotion_history: list[tuple[float, Emotion]] = []  # (time, emotion)
    
    def update_from_beats(self, beats: list) -> None:
        """Process all beats and evolve state continuously."""
        pass
    
    def get_pose_at_time(self, scene_time: float) -> CharacterPose:
        """Get pose incorporating persistent state + scene emotion."""
        pass
```

### State Transitions

```
Initial (neutral): confidence=0.5, stress=0, energy=1.0

Paycheck scene (joy, intensity=0.6):
  → confidence += 0.2, stress -= 0.1, energy stable
  → carry "relief" into next scene

Tax scene (frustration, intensity=0.8):
  → confidence -= 0.3, stress += 0.4, energy -= 0.1
  → carry "resignation" into next scene

Housing scene (burden, intensity=0.7):
  → confidence -= 0.2, stress += 0.3, energy -= 0.2
  → carry "exhaustion" into final scene

Treadmill scene (despair, intensity=0.9):
  → confidence -> 0, stress -> max, energy -> min
  → character visibly depleted
```

### Implementation Strategy

1. **State initializer** — Parse beats to determine state trajectory
2. **Blending function** — Mix persistent state with scene-specific expression
3. **Transition curves** — Smooth state changes between scenes (no jumps)
4. **Visual mapping** — Map stress/energy/confidence to post-expression adjustments

### Benefits
- **Narrative continuity** — Character's emotional journey visible across full video
- **Cumulative impact** — Repeated financial pressures compound visually
- **Payoff power** — Final scene's exhaustion is earned, not arbitrary
- **Viewer empathy** — Audience sees character visibly affected by circumstances

---

## Phase 2.2 — Micro-expressions and Eye Direction

**Goal:** Add subtle facial feedback without redesigning the pictogram.

### Proposed Extensions

```python
@dataclass
class MicroExpression:
    """Subtle facial cues (eyes, mouth)."""
    eye_direction: float  # [-1, 1]: -1=left, 0=forward, 1=right
    brow_height: float    # [0, 1]: 0=normal, 1=raised (surprise/concern)
    mouth_shape: str      # "neutral", "frown", "grin"
```

### Implementation
- Eye glance direction tied to environmental focus (looking at prices, the road, etc.)
- Brow height as secondary emotion indicator (raised = concern, lowered = exhaustion)
- Mouth shape (frown/grin) as accent to primary emotion

### Example Flow
```
Gas station scene:
  Primary emotion: frustration (body posture)
  Eye direction: right (glancing at pump price)
  Brow height: 0.8 (raised in concern)
  Mouth: frown (subtle, supports frustration)
```

---

## Phase 2.3 — Activity-Based Pose Modulation

**Goal:** Tie pose to the scene's physical activity, not just emotion.

### Current State
Pose changes are emotion-driven only. Real behavior couples emotion with activity:
- Walking tired (exhaustion) = slower stride, drooping shoulders
- Waiting in traffic (frustration) = fidgeting, weight shifts, hand gestures
- Receiving money (joy) = expansive posture, energetic movement

### Proposed Additions

```python
def apply_activity(pose: CharacterPose, activity: str, intensity: float) -> CharacterPose:
    """Modulate pose based on activity context."""
    
    if activity == "walking":
        pose.stride = max(pose.stride, 0.3)  # Ensure walking gait
        pose.body_sway += 0.1 * intensity    # Natural sway
    
    elif activity == "waiting":
        pose.gesture_speed += 0.5 * intensity  # Fidgeting
        pose.body_sway = intensity * 0.3       # Weight shifts
    
    elif activity == "receiving":
        pose.arms_up = min(1.0, pose.arms_up + 0.4)  # Raised arms
        pose.stride = 0.6 * intensity             # Energetic
    
    return pose.clamp()
```

### Benefits
- Pose variation within a single emotion (joy expressed differently while walking vs. standing)
- Natural interaction between character state and scene activity
- Prevents pose repetition across similar-emotion scenes

---

## Phase 2.4 — Tension Release Events

**Goal:** Punctuate the narrative with visible emotional catharsis.

### Concept
Key moments where character's emotional state abruptly shifts:
- Receipt of unexpected good news
- Decision to change perspective
- Acceptance of circumstances

### Implementation

```python
class CatharticEvent:
    """Sudden emotional state shift."""
    time: float  # When it occurs
    emotion_from: Emotion
    emotion_to: Emotion
    transition_duration: float  # How long to ease in
    
def apply_cathartic(pose: CharacterPose, event: CatharticEvent,
                    scene_time: float) -> CharacterPose:
    """Apply cathartic transition."""
    if scene_time < event.time:
        return pose
    
    progress = min(1.0, (scene_time - event.time) / event.transition_duration)
    
    # Interpolate between emotions
    from_pose = emotion_to_pose_deltas(event.emotion_from)
    to_pose = emotion_to_pose_deltas(event.emotion_to)
    
    # Blend poses
    return blend_poses(from_pose, to_pose, progress)
```

### Example: The Realization
```
At t=20s (midway through video):
- Character realizes the treadmill metaphor
- Transitions from exhaustion → resignation
- Visible shift: shoulders drop, stride steadies, gaze lifts
- Viewers see acceptance, not defeat
```

---

## Phase 2.5 — Cross-Scene Continuity Tracking

**Goal:** Detect and prevent unwanted pose disruptions at scene cuts.

### Problem
Jumping from one emotion/activity to another can be jarring:
```
Scene N: exhaustion (arms_down, head_drop, slow)
Scene N+1: joy (arms_up, head_high, fast)
→ Abrupt cut looks like different character
```

### Solution

```python
def smooth_scene_transition(pose_out: CharacterPose,
                            pose_in: CharacterPose,
                            transition_duration: float = 0.2) -> CharacterPose:
    """Interpolate between scenes to smooth the cut."""
    # Implementation: ease in/out over 200ms
    pass
```

---

## Phase 3 — Advanced: Behavioral Learning

**Goal:** Train the expression system from human performance data.

### Future Work
- Collect poses from reference video (human actor performing scenarios)
- Use ML to map emotions to optimal pose parameters
- Learn nuanced transitions and micro-movements
- Adapt to story context (different poses for same emotion in different scenes)

### Data Collection
```
Input: Video clips of human performing emotional scenarios
  - Financial stress
  - Hope
  - Resignation
  - Exhaustion

Output: Annotated pose parameters + emotional labels
  → Train neural net to predict pose from (emotion, activity, stress_level)
```

---

## Maintenance & Testing

### Unit Tests to Add
```python
# Future test suite
test_persistent_state_update()        # State evolves correctly
test_micro_expression_blending()      # Eyes/brows render correctly
test_activity_pose_modulation()       # Activities modulate pose
test_cathartic_transition()           # Emotional shifts are smooth
test_scene_transition_continuity()    # Cuts don't jar
```

### Integration Tests
```python
test_full_narrative_arc()      # State journey across all scenes
test_stress_accumulation()     # Cumulative effects over time
test_emotional_payoff()        # Final scene matches narrative peak
```

### Performance Benchmarks
Current: 2.5x realtime for simple emotions
Target: <4x realtime for persistent state + micro-expressions

---

## Decision Log

### Why Not Speech-Sync Lip Animation?
- **Reason not chosen:** The pictogram is abstract; adding lip-sync creates uncanny valley
- **Alternative:** Micro-expressions (eyes/brows) sufficient for subtle character
- **Future:** Revisit only if we redesign to more realistic character model

### Why Not Auto-Detect Emotions from Narration?
- **Reason not chosen:** Requires NLP + semantic understanding; adds complexity
- **Current approach:** Author emotions manually with beat intent (more control)
- **Future:** NLP emotion detection could auto-populate, with manual override

### Why Not Animate All Pictograms?
- **Current:** Only money-story pictogram has expressions
- **Decision:** Other stories use different visual languages (charts, footage, scenes)
- **Future:** Extend to treadmill-character and other recurring figures

---

## Success Metrics

A successful persistent-state system will achieve:
1. **Emotional continuity** — Viewers sense character's emotional journey
2. **Zero jarring cuts** — Scene transitions feel natural
3. **Performance** — <4x realtime, no render slowdown regression
4. **Maintainability** — Expression config remains simple (no magic numbers)
5. **Reusability** — Works for any story with a recurring character

---

## References

- `data_learning/expression.py` — Current implementation
- `scripts/test_expressions.py` — Phase 3 tests
- `scripts/verify_expression_gates.py` — Phase 8-9 gates
- `data_learning/scenes.py` — Scene implementations using expressions

---

*Last updated after Phase 10 completion. Ready for Phase 2.1 design work in next iteration.*
