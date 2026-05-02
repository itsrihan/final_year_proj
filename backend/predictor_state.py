from enum import Enum, auto


class PredictorState(Enum):
    IDLE = auto()
    REENTRY = auto()
    SIGNING = auto()
    CONFIRMED = auto()
    HOLD = auto()  # Added: display confirmed label for HOLD_FRAMES before re-signing