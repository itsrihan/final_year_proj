from enum import Enum, auto


class PredictorState(Enum):
    IDLE = auto()
    REENTRY = auto()
    SIGNING = auto()
    CONFIRMED = auto()
    HOLD = auto()  


class CaptureState(Enum):
    """States for demo-stable capture and prediction."""
    READY = auto()
    CAPTURING = auto()
    PREDICTING = auto()
    WAIT_FOR_RELEASE = auto()
