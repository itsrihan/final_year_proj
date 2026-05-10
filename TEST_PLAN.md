# Test Plan - Priority Fixes Validation

## Pre-Test Setup
- Backend running on `localhost:8001`
- Frontend running on `localhost:5173` (dev mode) or `localhost:5173` (prod)
- Camera permissions enabled
- Browser console open to monitor errors and logs
- Backend terminal visible to see prediction logs

---

## Test Scenario 1: Camera OFF = No Random Words
**Objective:** Verify camera-off hard reset prevents stale predictions

**Steps:**
1. Start with camera ON, ASL enabled
2. Perform a sign (e.g., "hello")
3. Wait for prediction to show (e.g., "hello" with 0.87 confidence)
4. Wait for WAIT_FOR_RELEASE state (ring should be amber/red)
5. **Turn camera OFF** → ring should turn off (no glow)
6. Check response: text should be "Waiting...", confidence 0.0, state should be "ready"
7. Keep camera off for 30 seconds
8. Turn camera back ON
9. **Verify:** Text should still be "Waiting..." (not showing old "hello")
   - Ring should be GREEN (ready state)
   - No random words in captions

**Expected JSON (camera off):**
```json
{
  "text": "Waiting...",
  "confidence": 0.0,
  "status": "Camera off",
  "asl_capture_state": "ready",
  "captured_frames": 0,
  "required_frames": 45
}
```

**Expected backend log:**
```
[CAPTURE] Hard reset to READY (camera-off or other trigger)
```

---

## Test Scenario 2: No Hand = No Prediction
**Objective:** Verify system doesn't predict with no hands visible

**Steps:**
1. Start with camera ON, ASL enabled
2. **Keep hands out of frame** for 10+ seconds
3. Check response: text should be "Waiting...", confidence 0.0
4. Ring should be GREEN (ready state)
5. `hands_detected` should be false, `captured_frames` should be 0
6. Move hand into frame but hold still (no motion) for 5 seconds
7. **Verify:** Still "Waiting...", no prediction attempt
8. Perform the sign

**Expected behavior:**
- Ring stays GREEN while no hands present
- No frames captured
- No inference runs

---

## Test Scenario 3: One Sign = One Prediction
**Objective:** Verify clean single prediction flow

**Steps:**
1. Start camera ON, ASL enabled (ring GREEN)
2. Perform one clear sign (e.g., "hello")
3. Hand visible for ~45 frames (1.5 seconds at 30fps)
4. **Observe ring color sequence:**
   - GREEN (ready, debouncing hand)
   - RED (capturing 0-45/45)
   - RED (predicting, running inference)
   - AMBER/RED (wait_for_release, showing prediction)
5. Check text shows the prediction (e.g., "hello")
6. Confidence should be high (>0.60)
7. **Verify:** Only ONE prediction log line appears in backend:
   ```
   [PREDICT] raw_label=hello, raw_confidence=0.8734, final_display=hello, 
             captured_raw_frames=45, model_frames=35, state=PREDICTING, accepted=True
   ```

**Expected behavior:**
- Single clean inference, no repeated predictions
- Correct frame counts (45 raw, 35 model)
- State transitions visible in logs

---

## Test Scenario 4: Hand Remains = Wait_For_Release (No Repeat)
**Objective:** Verify WAIT_FOR_RELEASE prevents repeated capture while hand visible

**Steps:**
1. Perform sign "hello" → prediction shown
2. Ring is AMBER/RED (wait_for_release state)
3. **Keep hand visible and still** (do NOT repeat the sign)
4. Wait 30 seconds
5. **Verify:** Text still shows "hello" (same prediction)
6. Check backend logs: should see NO additional [PREDICT] lines
7. Check response: `asl_capture_state` should remain "wait_for_release"
8. `captured_frames` should be 0 (cleared after prediction)

**Expected behavior:**
- No repeated predictions while hand visible
- Ring stays AMBER/RED (wait_for_release)
- Same prediction text shown throughout
- Backend logs show no new inference attempts

---

## Test Scenario 5: Hand Removed = Ready Again
**Objective:** Verify state machine cycles back to READY after hand release

**Steps:**
1. Perform sign "hello" → prediction shown (wait_for_release state)
2. Ring is AMBER/RED
3. **Remove hand completely from frame** (rapid motion)
4. Keep hand out of frame for 5+ seconds
5. **Observe ring color:**
   - Initially AMBER/RED (wait_for_release, hand just left)
   - After ~5 frames (5/5 release frames), should turn GREEN (ready)
6. Check response: `asl_capture_state` should be "ready", `release_counter` should reset
7. Text may still show "hello" briefly, then clear to "Waiting..."

**Expected backend logs:**
```
[CAPTURE] Release progress: 1/5
[CAPTURE] Release progress: 2/5
[CAPTURE] Release progress: 3/5
[CAPTURE] Release progress: 4/5
[CAPTURE] Release progress: 5/5
[CAPTURE] Release confirmed, returning to READY
```

---

## Test Scenario 6: Ring Color Changes Based on Backend State
**Objective:** Verify all state→color mappings work correctly

**Test ring color at each state:**

| Backend State | Ring Color | Visual |
|---|---|---|
| `ready` | GREEN | Solid glow |
| `capturing` | RED | Pulsing/solid glow |
| `predicting` | RED | Solid glow |
| `wait_for_release` | AMBER/RED | Amber glow |
| Camera OFF | OFF | No glow |

**Steps:**
1. Set up debug logging to show `asl_capture_state` in real-time
2. Slowly perform a sign, observing ring color changes
3. Watch ring match the state transitions in backend logs
4. Repeat with camera off to verify ring turns off

**Expected behavior:**
- Ring color 100% driven by backend `asl_capture_state`
- No color based on `handsCount` anymore
- Smooth transitions as state changes

---

## Test Scenario 7: Confidence Threshold = 0.60
**Objective:** Verify predictions below 0.60 show "Uncertain"

**Steps:**
1. Perform a sign ambiguously (sloppy motion, unclear gesture)
2. Inference completes with confidence < 0.60 (e.g., 0.55)
3. **Check text:** should show "Uncertain", NOT the label name
4. Check backend log:
   ```
   [PREDICT] raw_label=hello, raw_confidence=0.5500, final_display=Uncertain, ...
   ```
5. Perform same sign cleanly → confidence > 0.60
6. **Check text:** should show label name (e.g., "hello")
7. Check backend log:
   ```
   [PREDICT] raw_label=hello, raw_confidence=0.8700, final_display=hello, ...
   ```

**Expected behavior:**
- Model output with conf < 0.60 → display "Uncertain"
- Model output with conf >= 0.60 → display label
- Backend logs show raw vs display labels

---

## Test Scenario 8: Null Label Handling
**Objective:** Verify "null" predictions show "No clear sign"

**Precondition:** Model must have a "null" label in phrase_labels.json

**Steps:**
1. Perform nonsense gesture (not a valid sign)
2. Model predicts "null" with high confidence (e.g., 0.92)
3. **Check text:** should show "No clear sign", NOT "null"
4. Check backend log:
   ```
   [PREDICT] raw_label=null, raw_confidence=0.9200, final_display=No clear sign, ...
   ```
5. Perform a valid sign → model predicts label like "hello"
6. **Check text:** should show "hello"

**Expected behavior:**
- "null" predictions always map to "No clear sign"
- Never display the word "null" to user
- Backend logs show raw vs display mapping

---

## Test Scenario 9: 45-Frame Grace = Smoother Capture
**Objective:** Verify 45-frame capture and downsampling works

**Steps:**
1. Monitor backend logs for capture progress
2. Perform a sign
3. **Check logs:** should see progress like:
   ```
   [CAPTURE] Progress: 5/45 frames
   [CAPTURE] Progress: 10/45 frames
   [CAPTURE] Progress: 15/45 frames
   ...
   [CAPTURE] Progress: 45/45 frames
   [CAPTURE] Capture complete, 45 frames collected, starting PREDICTING
   ```
4. Check response `captured_frames` field:
   - During capture: should show 0-45
   - After prediction: should be 0 (cleared)
5. In backend, verify downsampling happens:
   ```
   [PREDICT] ... captured_raw_frames=45, model_frames=35 ...
   ```

**Expected behavior:**
- Capture waits for 45 frames (more grace, smoother)
- Downsampling reduces 45 → 35 internally
- Model always gets (1, 35, 195) input
- Logs show frame counts clearly

---

## Quick Sanity Checks

Run these quick checks to verify nothing broke:

1. **Frontend loads without errors**
   - No console errors on page load
   - Camera permission requested properly
   - ASL indicator ring renders

2. **Backend accepts frames**
   - Backend logs show incoming frames
   - No crash on frame receive

3. **First prediction works**
   - Perform a sign
   - Text updates with prediction
   - Confidence shows reasonable value
   - Ring color changes through states

4. **State machine transitions**
   - ready → capturing → predicting → wait_for_release → ready
   - No stuck states
   - Logs show clean transitions

---

## Failure Checklist

If any test fails, check:

- [ ] Backend logs for error messages
- [ ] Frontend console for JavaScript errors
- [ ] Network tab for WebSocket errors
- [ ] Response JSON structure (all required fields present?)
- [ ] `asl_capture_state` values match expected (lowercase, no typos)
- [ ] Model is loaded and accessible
- [ ] Camera permissions granted
- [ ] No concurrent modifications to CaptureStateMachine

---

## Test Report Template

For each scenario, document:
- **Scenario:** [name]
- **Steps:** [what you did]
- **Expected:** [what should happen]
- **Actual:** [what actually happened]
- **Result:** ✓ PASS / ✗ FAIL
- **Notes:** [any anomalies]
- **Backend Log:** [relevant log lines]
- **JSON Response:** [sample response received]

---

## Next Steps After Passing Tests
1. Verify all 9 scenarios pass
2. Check backend logs for any warnings or errors
3. Confirm no random words appear at any point
4. Ensure ring color is always correct
5. Then: Ready to commit
