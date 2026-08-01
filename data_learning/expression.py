#!/usr/bin/env python3
"""EXPRESSION SYSTEM — structured character emotional states.

Defines reusable emotion configurations and pose parameters for the pictogram character.
Keeps emotion logic separate from scene rendering so it's portable and testable.
"""

from dataclasses import dataclass
from typing import Literal

# Supported emotion names
Emotion = Literal[
    "joy",
    "shock",
    "resignation",
    "frustration",
    "burden",
    "exhaustion",
    "relief",
]

# Pose parameter names and their safe ranges
PoseParams = Literal["arms_up", "stride", "lean", "head_drop", "body_sway", "gesture_speed"]


@dataclass
class ExpressionConfig:
    """Structured character emotional expression.

    Args:
        emotion: Named emotion state (joy, shock, resignation, etc.)
        start: Time in [0, 1] when expression begins ramping (0=immediately)
        end: Time in [0, 1] when expression ends ramping (1=full beat)
        intensity: Strength in [0, 1.0]; 0=no change, 1=maximum expression

    All fields have safe defaults; missing fields are filled from baseline.
    """

    emotion: Emotion = "resignation"
    start: float = 0.0
    end: float = 1.0
    intensity: float = 0.7

    def __post_init__(self):
        """Clamp all values to safe ranges."""
        self.start = max(0.0, min(1.0, self.start))
        self.end = max(0.0, min(1.0, self.end))
        self.intensity = max(0.0, min(1.0, self.intensity))
        if self.end < self.start:
            self.start, self.end = self.end, self.start


@dataclass
class CharacterPose:
    """Clamped pose parameters for the pictogram.

    Each parameter is bounded to prevent anatomically impossible or bizarre poses.
    All are initialized to neutral (0 or 0.5 depending on the parameter).
    """

    arms_up: float = 0.3  # [0, 1]: 0=arms down, 1=arms raised above head
    stride: float = 0.5  # [0, 1]: 0=standing still, 1=walking fast
    lean: float = 0.0  # [-1, 1]: -1=leaning left, 0=upright, 1=leaning right
    head_drop: float = 0.0  # [0, 1]: 0=head up, 1=head drooped to chest
    body_sway: float = 0.0  # [-1, 1]: side-to-side weight shift
    gesture_speed: float = 1.0  # [0.5, 2]: 0.5=slow/tired, 1=normal, 2=agitated

    def clamp(self):
        """Enforce safe bounds on all parameters."""
        self.arms_up = max(0.0, min(1.0, self.arms_up))
        self.stride = max(0.0, min(1.0, self.stride))
        self.lean = max(-1.0, min(1.0, self.lean))
        self.head_drop = max(0.0, min(1.0, self.head_drop))
        self.body_sway = max(-1.0, min(1.0, self.body_sway))
        self.gesture_speed = max(0.5, min(2.0, self.gesture_speed))
        return self


def emotion_to_pose_deltas(
    emotion: Emotion, intensity: float = 0.7
) -> CharacterPose:
    """Map an emotion to pose changes.

    Returns pose DELTAS (offsets from neutral), not final pose.
    Caller should apply over base pose and clamp result.

    Args:
        emotion: Named emotion state
        intensity: Strength [0, 1]

    Returns:
        CharacterPose with deltas (may exceed bounds; caller clamps)
    """
    intensity = max(0.0, min(1.0, intensity))

    if emotion == "joy":
        return CharacterPose(
            arms_up=0.4 * intensity,
            stride=0.15 * intensity,
            gesture_speed=1.3 * intensity,
        )
    elif emotion == "shock":
        return CharacterPose(
            arms_up=0.5 * intensity,
            head_drop=-0.2 * intensity,
            gesture_speed=1.5 * intensity,
        )
    elif emotion == "resignation":
        return CharacterPose(
            arms_up=-0.2 * intensity,
            head_drop=0.3 * intensity,
            gesture_speed=0.7 * intensity,
        )
    elif emotion == "frustration":
        return CharacterPose(
            arms_up=0.3 * intensity,
            gesture_speed=1.4 * intensity,
            body_sway=0.2 * intensity,
        )
    elif emotion == "burden":
        return CharacterPose(
            stride=0.3 * intensity,
            lean=0.1 * intensity,
            gesture_speed=0.8 * intensity,
        )
    elif emotion == "exhaustion":
        return CharacterPose(
            arms_up=-0.3 * intensity,
            stride=-0.2 * intensity,
            head_drop=0.4 * intensity,
            gesture_speed=0.6 * intensity,
        )
    elif emotion == "relief":
        return CharacterPose(
            arms_up=0.3 * intensity,
            stride=0.1 * intensity,
            gesture_speed=1.2 * intensity,
        )
    else:
        return CharacterPose()  # Neutral fallback


def apply_expression(
    base_pose: CharacterPose,
    expression: ExpressionConfig,
    beat_time: float,
) -> CharacterPose:
    """Apply expression progression over a beat.

    Linearly interpolates emotion strength based on beat_time within
    expression.start and expression.end window.

    Args:
        base_pose: Starting pose (often neutral)
        expression: Expression config with timing and emotion
        beat_time: Current time within beat [0, 1]

    Returns:
        Interpolated CharacterPose with clamped values
    """
    if beat_time < expression.start or beat_time > expression.end:
        return base_pose

    if expression.end <= expression.start:
        return base_pose

    # Interpolation within the active window
    window_width = expression.end - expression.start
    progress = (beat_time - expression.start) / window_width
    progress = max(0.0, min(1.0, progress))

    # Get the pose deltas for this emotion at this intensity
    deltas = emotion_to_pose_deltas(expression.emotion, expression.intensity)

    # Apply deltas to base pose
    result = CharacterPose(
        arms_up=base_pose.arms_up + deltas.arms_up * progress,
        stride=base_pose.stride + deltas.stride * progress,
        lean=base_pose.lean + deltas.lean * progress,
        head_drop=base_pose.head_drop + deltas.head_drop * progress,
        body_sway=base_pose.body_sway + deltas.body_sway * progress,
        gesture_speed=base_pose.gesture_speed + (deltas.gesture_speed - 1.0) * progress,
    )

    return result.clamp()


def parse_expression_config(extra: dict | None) -> ExpressionConfig | None:
    """Parse expression config from beat extra field.

    Accepts both legacy Boolean format and new structured format:

    Legacy (backward compatible):
        {"express": true}  -> ExpressionConfig(emotion="resignation")

    Structured:
        {"expression": {"emotion": "joy", "intensity": 0.8, ...}}

    Args:
        extra: Beat's extra dict (or None)

    Returns:
        ExpressionConfig if expression is enabled, None otherwise
    """
    if not extra:
        return None

    # New structured format
    if "expression" in extra:
        expr_dict = extra["expression"]
        if isinstance(expr_dict, dict):
            return ExpressionConfig(**{k: v for k, v in expr_dict.items()})

    # Legacy Boolean format (backward compatible)
    if extra.get("express"):
        return ExpressionConfig(emotion="resignation", intensity=0.7)

    return None
