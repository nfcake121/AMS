"""Arms strategy handlers."""

from src.builders.blender.components.arms_strategies.arm_box import build_arm_box_strategy
from src.builders.blender.components.arms_strategies.arm_frame_box_open import (
    build_arm_frame_box_open_strategy,
)

__all__ = [
    "build_arm_box_strategy",
    "build_arm_frame_box_open_strategy",
]
