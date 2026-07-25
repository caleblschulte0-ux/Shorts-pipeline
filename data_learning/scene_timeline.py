"""ONE scene timeline, owned by the scene director (ChatGPT review §4).

Chart growth, mascot choreography, labels and SFX used to be animated as
separate systems and composited afterwards — each guessing its own timing.
This module is the single owner of a scene's clock: everything that moves in a
beat reads its phase boundaries and event times from here.

``PHASES`` is the canonical setup -> effort -> payoff split of a beat as
fractions of the beat.  The mascot's coupled/arc animators derive their zone
boundaries from these values (mascot_director imports them), the charts drive
the same fractions through ``reveal``, and the renderer records the concrete
event list (seconds) into the manifest so a scene's plan is inspectable.

``plan_scene`` turns (kind, action, duration) into the explicit event list —
"{t, actor, action, target, driver}" — the renderer executes. The renderer does
not independently guess timing.
"""
from __future__ import annotations

# Canonical beat phases (fractions of the beat). SINGLE SOURCE OF TRUTH:
# mascot_director's animators and the chart reveal both read these.
SETUP_END = 0.18          # settle into the wind-up / grip
EFFORT_END = 0.74         # repeated effort / being driven by the data
#                p >= EFFORT_END is the payoff (reversal + reaction)

PHASES = {
    "setup": (0.0, SETUP_END),
    "effort": (SETUP_END, EFFORT_END),
    "payoff": (EFFORT_END, 1.0),
}

# The hook burst: the opening chart shoots to this reveal fraction within the
# first HOOK_BURST_T of the beat (frame-1 motion, "primary action before 0.4s").
HOOK_BURST_T = 0.22
HOOK_BURST_REVEAL = 0.46


def phase_at(p: float) -> str:
    """Which phase a beat-progress p in [0,1] falls in."""
    if p < SETUP_END:
        return "setup"
    if p < EFFORT_END:
        return "effort"
    return "payoff"


def plan_scene(kind: str, action: str, duration: float,
               target: str = "", goal: str = "") -> dict:
    """The explicit event timeline for one scene: who does what, when, to what,
    and what DRIVES what. The mascot's action is CAUSED by / RESISTED BY the
    data object's growth — the coupling the renderer executes."""
    d = max(0.5, float(duration))
    t_setup = round(SETUP_END * d, 2)
    t_payoff = round(EFFORT_END * d, 2)
    obj = target or "datum_0"
    events = [
        {"t": 0.0, "actor": "chart", "action": "enter", "target": obj},
        {"t": 0.0, "actor": "data", "action": "grip", "target": obj,
         "contact": "both_hands"},
        {"t": 0.0, "actor": obj, "action": "grow", "driver": "data_reveal"},
        {"t": t_setup, "actor": "data", "action": action, "target": obj,
         "driver": obj},                       # the data object drives his body
        {"t": t_payoff, "actor": "data", "action": "payoff_reaction",
         "target": obj},
        {"t": t_payoff, "actor": "label", "action": "land", "target": obj},
        {"t": round(d, 2), "actor": "chart", "action": "final_state"},
    ]
    return {"duration": round(d, 2), "kind": kind, "action": action,
            "goal": goal, "target": obj, "phases": {
                k: [round(a * d, 2), round(b * d, 2)]
                for k, (a, b) in PHASES.items()},
            "events": events}
