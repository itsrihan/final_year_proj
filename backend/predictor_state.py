from enum import Enum, auto


class PredictorState(Enum):
    IDLE = auto()
    REENTRY = auto()
    SIGNING = auto()
    CONFIRMED = auto()
