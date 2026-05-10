# Summary of Changes - Priority Fixes Implementation

**Date:** May 8, 2026  
**Focus:** Camera-off reset, ring color fix, 45-frame grace, 0.60 threshold, logging

---

## 1. Camera-Off Hard Reset

### Frontend Changes: `frontend/src/hooks/useAslStream.js`
- **OLD:** Frame send loop returned early if `!cameraOn`, but no message was sent
- **NEW:** Always sends a frame (even when camera off), but includes `camera_on` flag:
  - When camera ON: `{ frame: <base64>, asl_enabled: true, camera_on: true }`
  - When camera OFF: `{ frame: null, asl_enabled: true, camera_on: false }`

### Backend Changes: `backend/main.py`
- Extracts `camera_on = payload.get("camera_on", True)` from message
- If `camera_on == false` OR `frame_data is None`:
  - Calls `capture_machine.reset()` to hard reset state machine
  - Returns immediate response with state=ready, text="Waiting...", confidence=0.0
  - No landmark extraction or inference happens

### New Backend Method: `backend/predictor_engine.py` - `CaptureStateMachine.reset()`
```python
def reset(self):
    """Hard reset the capture machine to READY state (used for camera-off)."""
    self.state = CaptureState.READY
    self.captured_frames = []
    self.last_valid_features = None
    self.hand_debounce_frames = 0
    self.missed_frames_during_capture = 0
    self.last_prediction = ("", 0.0)
    self.release_counter = 0
    self._last_prediction_accepted = False
```

---

## 2. Frontend Ring Color Fix

### File: `frontend/src/components/meeting/MeetingVideoStage.jsx`
**Mapping:**
- `asl_capture_state == "ready"` → `indicatorState = "ready"` → **GREEN**
- `asl_capture_state == "capturing"` → `indicatorState = "translating"` → **RED**
- `asl_capture_state == "predicting"` → `indicatorState = "translating"` → **RED**
- `asl_capture_state == "wait_for_release"` → `indicatorState = "hand-detected"` → **AMBER/RED**
- Otherwise → `indicatorState = "off"` → **NO GLOW**

Ring color logic NO LONGER uses `handsCount` — entirely backend-driven via `asl_capture_state`.

---

## 3. 45-Frame Capture Grace with Downsampling

### Backend: `backend/predictor_engine.py`
**New constants:**
```python
CAPTURE_TARGET_FRAMES = 45  # Grace: collect 45, then downsample to 35 for model
MODEL_FRAMES = 35           # Model always takes 35 frames
```

**CAPTURING state now waits for 45 frames** (was 35):
- `if len(self.captured_frames) >= self.CAPTURE_TARGET_FRAMES:` → transition to PREDICTING

**PREDICTING state now downsamples before inference:**
```python
# Downsample 45 frames to 35 for model input using linear interpolation
indices = np.linspace(0, len(self.captured_frames) - 1, self.MODEL_FRAMES).astype(int)
downsampled_frames = np.asarray(self.captured_frames, dtype=np.float32)[indices]
model_input = np.expand_dims(downsampled_frames, axis=0)  # (1, 35, 195)
```

**Response field updated:**
```python
'required_frames': self.CAPTURE_TARGET_FRAMES,  # Show 45 to user, not 35
```

---

## 4. Confidence & Null Handling

### Backend: `backend/predictor_engine.py`
**New threshold: 0.60** (was 0.70)

**Display rules in PREDICTING state:**
```python
ACCEPT_THRESHOLD = 0.60
display_label = label
if label == "null":
    display_label = "No clear sign"
elif confidence < ACCEPT_THRESHOLD:
    display_label = "Uncertain"

accepted = (label != "null" and confidence >= ACCEPT_THRESHOLD)
```

**Results:**
- Model predicts "null" → display "No clear sign"
- Model predicts any label with confidence < 0.60 → display "Uncertain"
- Model predicts label with confidence >= 0.60 and label != "null" → display label
- Only predictions with `accepted=True` count toward anything (though frontend shows display_label always)

---

## 5. Enhanced Prediction Logging

### Backend: `backend/predictor_engine.py` - PREDICTING state
Log line now includes:
```
[PREDICT] raw_label={label}, raw_confidence={confidence:.4f}, 
          final_display={display_label}, captured_raw_frames={len(captured_frames)}, 
          model_frames={MODEL_FRAMES}, state=PREDICTING, accepted={accepted}
```

**Example log:**
```
[PREDICT] raw_label=hello, raw_confidence=0.8734, final_display=hello, 
          captured_raw_frames=45, model_frames=35, state=PREDICTING, accepted=True
```

---

## Sample JSON Responses

### State: READY (Green)
```json
{
  "text": "Waiting...",
  "confidence": 0.0,
  "status": "ASL on | ready",
  "model_name": "phrase_lstm.keras",
  "hands_detected": false,
  "hands_count": 0,
  "predictor_ready": true,
  "predictor_error": null,
  "inference_device": "gpu",
  "inference_mode": "ready",
  "asl_capture_state": "ready",
  "captured_frames": 0,
  "required_frames": 45,
  "hand_debounce_frames": 0
}
```

### State: CAPTURING 30/45 (Red)
```json
{
  "text": "Translating...",
  "confidence": 0.0,
  "status": "ASL on | capturing 30/45",
  "model_name": "phrase_lstm.keras",
  "hands_detected": true,
  "hands_count": 1,
  "predictor_ready": true,
  "predictor_error": null,
  "inference_device": "gpu",
  "inference_mode": "capturing",
  "asl_capture_state": "capturing",
  "captured_frames": 30,
  "required_frames": 45,
  "hand_debounce_frames": 2
}
```

### State: PREDICTING (after 45 frames captured, inference complete) (Red)
```json
{
  "text": "hello",
  "confidence": 0.8734,
  "status": "ASL on | predicting",
  "model_name": "phrase_lstm.keras",
  "hands_detected": true,
  "hands_count": 1,
  "predictor_ready": true,
  "predictor_error": null,
  "inference_device": "gpu",
  "inference_mode": "predicting",
  "asl_capture_state": "wait_for_release",
  "captured_frames": 0,
  "required_frames": 45,
  "hand_debounce_frames": 0
}
```

### State: WAIT_FOR_RELEASE (Amber/Red - showing prediction from previous inference)
```json
{
  "text": "hello",
  "confidence": 0.8734,
  "status": "ASL on | wait_for_release (release hand to repeat)",
  "model_name": "phrase_lstm.keras",
  "hands_detected": true,
  "hands_count": 1,
  "predictor_ready": true,
  "predictor_error": null,
  "inference_device": "gpu",
  "inference_mode": "wait_for_release",
  "asl_capture_state": "wait_for_release",
  "captured_frames": 0,
  "required_frames": 45,
  "hand_debounce_frames": 0
}
```

### State: WAIT_FOR_RELEASE 3/5 (hand released, counting down) (Amber/Red)
```json
{
  "text": "hello",
  "confidence": 0.8734,
  "status": "ASL on | wait_for_release (release hand to repeat)",
  "model_name": "phrase_lstm.keras",
  "hands_detected": false,
  "hands_count": 0,
  "predictor_ready": true,
  "predictor_error": null,
  "inference_device": "gpu",
  "inference_mode": "wait_for_release",
  "asl_capture_state": "wait_for_release",
  "captured_frames": 0,
  "required_frames": 45,
  "hand_debounce_frames": 0
}
```

### State: Camera OFF (Green indicator off)
```json
{
  "text": "Waiting...",
  "confidence": 0.0,
  "status": "Camera off",
  "model_name": "phrase_lstm.keras",
  "asl_capture_state": "ready",
  "captured_frames": 0,
  "required_frames": 45,
  "hands_detected": false,
  "hand_debounce_frames": 0
}
```

### Edge Case: Prediction with confidence < 0.60
```json
{
  "text": "Uncertain",
  "confidence": 0.5234,
  "status": "ASL on | wait_for_release (release hand to repeat)",
  "model_name": "phrase_lstm.keras",
  "hands_detected": true,
  "hands_count": 1,
  "predictor_ready": true,
  "predictor_error": null,
  "inference_device": "gpu",
  "inference_mode": "wait_for_release",
  "asl_capture_state": "wait_for_release",
  "captured_frames": 0,
  "required_frames": 45,
  "hand_debounce_frames": 0
}
```

### Edge Case: Model predicts "null"
```json
{
  "text": "No clear sign",
  "confidence": 0.9112,
  "status": "ASL on | wait_for_release (release hand to repeat)",
  "model_name": "phrase_lstm.keras",
  "hands_detected": true,
  "hands_count": 1,
  "predictor_ready": true,
  "predictor_error": null,
  "inference_device": "gpu",
  "inference_mode": "wait_for_release",
  "asl_capture_state": "wait_for_release",
  "captured_frames": 0,
  "required_frames": 45,
  "hand_debounce_frames": 0
}
```

---

## Files Modified

1. **backend/predictor_engine.py**
   - Added `CAPTURE_TARGET_FRAMES = 45` and `MODEL_FRAMES = 35`
   - Added `reset()` method to CaptureStateMachine
   - Updated `_handle_capturing()` to target 45 frames
   - Updated `_handle_predicting()` to downsample 45→35 and apply 0.60 threshold
   - Enhanced logging with raw_label, display_label, frame counts, state, acceptance
   - Updated `_make_response()` to report `required_frames: 45`

2. **backend/main.py**
   - Extract `camera_on` from payload
   - Call `capture_machine.reset()` when camera_on=false
   - Update required_frames from 35 to 45 in all response dicts
   - Update WAIT_FOR_RELEASE status message

3. **frontend/src/hooks/useAslStream.js**
   - Always send frame messages (even when camera off)
   - Include `camera_on` and `frame` flags in JSON
   - Send reset message when camera turns off

4. **frontend/src/components/meeting/MeetingVideoStage.jsx**
   - Add "wait_for_release" case (map to hand-detected/amber)
   - Remove "cooldown" case (replaced by wait_for_release)
   - Ensure ring color is driven by `asl_capture_state` only

---

## Ready for Testing

All changes compiled and built successfully.
Frontend build: ✓ 43 modules, no errors
Backend syntax check: ✓ No Python syntax errors

Next: Run actual test cases to verify behavior.
