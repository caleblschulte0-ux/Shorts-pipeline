from __future__ import annotations

from .models import TensionBeat, TensionPlan

ROLE_BASE = {
    "hook": (78, 88, 30, 0),
    "setup": (52, 50, 38, 5),
    "explanation": (62, 42, 55, 5),
    "consequence": (86, 30, 92, 0),
    "payoff": (54, 5, 72, 78),
}


def _event_modifier(event: str) -> tuple[float, float, float]:
    low = event.lower()
    intensity = 8 if any(token in low for token in ("slam", "collision", "race", "squeeze")) else 0
    uncertainty = 8 if any(token in low for token in ("gap", "line", "trend")) else 0
    consequence = 10 if any(token in low for token in ("stack", "burden", "cart", "overflow")) else 0
    return intensity, uncertainty, consequence


def compile_tension(scenes: tuple[dict, ...]) -> TensionPlan:
    beats: list[TensionBeat] = []
    for index, scene in enumerate(scenes):
        role = str(scene["role"])
        base = ROLE_BASE[role]
        mi, mu, mc = _event_modifier(str(scene.get("visual_event", "")))
        progress = index / max(1, len(scenes) - 1)
        beat = TensionBeat(
            scene_id=str(scene.get("scene_id", f"seg{index:02d}")),
            role=role,
            intensity=min(100, base[0] + mi + progress * 7),
            uncertainty=min(100, base[1] + mu - progress * 8),
            consequence=min(100, base[2] + mc + progress * 10),
            release=min(100, base[3] + (progress * 8 if role == "payoff" else 0)),
        )
        beats.append(beat)

    nets = [beat.net for beat in beats]
    peak_index = max(range(len(nets)), key=nets.__getitem__)
    plateaus = sum(1 for a, b in zip(nets, nets[1:]) if abs(a - b) < 4)
    payoff_drop = round(max(nets[:-1]) - nets[-1], 1)
    plan = TensionPlan(tuple(beats), beats[peak_index].scene_id, payoff_drop, plateaus)
    plan.validate()
    return plan


def tension_score(plan: TensionPlan) -> float:
    nets = [beat.net for beat in plan.beats]
    early_hook = 100 if nets[0] >= 55 else nets[0] / 55 * 100
    consequence_peak = 100 if plan.beats[-2].role == "consequence" and plan.peak_scene == plan.beats[-2].scene_id else 72
    release = min(100, plan.payoff_drop / 25 * 100)
    plateau = max(0, 100 - plan.plateau_count * 35)
    return round(early_hook * .25 + consequence_peak * .30 + release * .30 + plateau * .15, 1)
