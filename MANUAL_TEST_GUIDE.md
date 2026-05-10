# MANUAL TEST GUIDE - Run These Steps in Your Running App

## Prerequisites
- Backend: Running on `localhost:8001` ✓
- Frontend: Running and loaded ✓
- Camera: Permissions granted
- Browser console: Open (F12 → Console tab)
- Backend terminal: Visible to see logs

---

## QUICK VERIFICATION (Run First - 2 minutes)

### 1. **Camera OFF → Hard Reset**
1. Open app, enable camera and ASL
2. Perform a sign (wait for prediction, e.g., "hello")
3. **Turn camera OFF** using the UI toggle
4. **Check immediately:**
   - Ring glow should **turn OFF** (no glow)
   - Text should show **"Waiting..."** (not old prediction)
   - Confidence should be **0.0**
   - Browser console: No JavaScript errors
5. **Backend check:**
   - Look for log: `[CAPTURE] Hard reset to READY (camera-off or other trigger)`

**Result:** ✓ PASS if camera off resets cleanly / ✗ FAIL if shows old prediction

---

### 2. **Ring Color Follows Backend State**
1. Keep app running, camera ON, ASL enabled
2. **Observe ring color sequence when you perform a sign:**
   - **GREEN** (ready, waiting for hands)
   - **RED** (capturing, collecting frames)
   - **RED** (predicting, running inference)
   - **AMBER/RED** (wait_for_release, showing result)
   - Back to **GREEN** (after hand removed for 5+ frames)

3. **Turn camera OFF:**
   - Ring should turn **OFF** (no glow at all)

**Expected behavior:** Ring changes exactly match states above

**Result:** ✓ PASS if ring colors match states / ✗ FAIL if colors wrong or based on hand count

---

### 3. **One Sign = One Prediction (No Repeats)**
1. Start fresh, camera ON, ASL enabled (ring GREEN)
2. **Perform ONE clear sign (e.g., "hello") - keep hand visible for ~2 seconds**
3. Watch text update to the predicted word
4. Ring shows: GREEN → RED → RED → AMBER/RED
5. **Check backend logs:**
   - Should see **exactly ONE** line with `[PREDICT]`
   - Example:
     ```
     [PREDICT] raw_label=hello, raw_confidence=0.8734, final_display=hello, 
               captured_raw_frames=45, model_frames=35, state=PREDICTING, accepted=True
     ```
6. **Keep hand visible and still** for 30 more seconds
7. **Check logs again:**
   - Should see **NO additional** `[PREDICT]` lines
   - Ring should stay AMBER/RED (wait_for_release state)

**Expected behavior:**
- Single clean inference, no repeated predictions
- Frame counts show 45 captured, 35 model
- Staying still = no re-prediction

**Result:** ✓ PASS if one prediction only / ✗ FAIL if multiple predictions or repeated capture

---

## DETAILED TESTING (If Quick Tests Pass - 10 minutes)

### 4. **No Hand = No Prediction**
1. Start app, camera ON, ASL enabled
2. **Keep hands COMPLETELY OUT of frame** for 30 seconds
3. Text should remain "Waiting..." (never changes)
4. Confidence should stay 0.0
5. Ring should stay **GREEN**
6. **Backend logs:** Should show no `[CAPTURE]` progress, no `[PREDICT]` lines

**Result:** ✓ PASS if no prediction without hands / ✗ FAIL if shows prediction

---

### 5. **Hand Removed = Return to READY (Release Sequence)**
1. Perform a sign → get prediction (ring AMBER/RED)
2. Text shows prediction (e.g., "hello")
3. **Remove hand completely from frame** (quick motion out)
4. **Watch ring color transitions:**
   - Stays AMBER/RED initially
   - After 5-6 frames (~0.2 seconds), should turn **GREEN**
5. **Check backend logs:**
   ```
   [CAPTURE] Release progress: 1/5
   [CAPTURE] Release progress: 2/5
   [CAPTURE] Release progress: 3/5
   [CAPTURE] Release progress: 4/5
   [CAPTURE] Release progress: 5/5
   [CAPTURE] Release confirmed, returning to READY
   ```
6. Text should gradually fade back to "Waiting..."

**Result:** ✓ PASS if release sequence works / ✗ FAIL if ring doesn't turn green or sequence broken

---

### 6. **Confidence Threshold = 0.60**
*This requires ambiguous signs or model uncertainty*

1. **Perform a SLOPPY/UNCLEAR sign** (messy hand motion, unclear gesture)
2. If model confidence < 0.60:
   - Text should show **"Uncertain"** (NOT a word)
   - Backend log: `raw_confidence=0.45` → `final_display=Uncertain`
3. **Repeat same sign CLEARLY** (deliberate, clean motion)
4. If model confidence >= 0.60:
   - Text should show **the label** (e.g., "hello")
   - Backend log: `raw_confidence=0.85` → `final_display=hello`

**Expected behavior:** Low confidence (< 0.60) always shows "Uncertain"

**Result:** ✓ PASS if threshold works / ✗ FAIL if shows label even with low confidence

---

### 7. **Null Label = "No clear sign"**
*This requires invalid/nonsense gesture or model quirk*

1. **Perform a completely invalid gesture** (random hand movement, not a real sign)
2. If model predicts "null" class:
   - Text should show **"No clear sign"** (NOT the word "null")
   - Backend log: `raw_label=null` → `final_display=No clear sign`
3. If it shows a valid label instead (model predicts something real), try again with different nonsense gesture

**Expected behavior:** Never display "null" to user

**Result:** ✓ PASS if null is hidden / ✗ FAIL if shows "null"

---

### 8. **45-Frame Grace Period**
1. Start capturing a sign
2. **Check backend logs:**
   - Should see:
     ```
     [CAPTURE] Progress: 5/45 frames
     [CAPTURE] Progress: 10/45 frames
     [CAPTURE] Progress: 15/45 frames
     [CAPTURE] Progress: 20/45 frames
     ...
     [CAPTURE] Progress: 45/45 frames
     [CAPTURE] Capture complete, 45 frames collected, starting PREDICTING
     ```
3. After prediction, check the log shows:
   ```
   [PREDICT] ... captured_raw_frames=45, model_frames=35 ...
   ```

**Expected behavior:**
- Progress shows 45, not 35
- Model gets 35 frames after downsampling
- Logs show both counts clearly

**Result:** ✓ PASS if 45-frame grace visible / ✗ FAIL if still shows 35

---

## Test Report Template

For **each scenario**, fill this out and paste results below:

```
## Scenario: [Name]
- **Steps:** [What I did]
- **Expected:** [What should happen]
- **Actual:** [What actually happened]
- **Result:** ✓ PASS / ✗ FAIL
- **Backend Logs:** [Relevant log lines]
- **Browser Console:** [Any errors?]
```

---

## Summary Checklist

After running all tests, check:

- [ ] Test 1: Camera OFF resets to READY
- [ ] Test 2: Ring color sequence correct
- [ ] Test 3: One sign = one prediction
- [ ] Test 4: No hand = no prediction
- [ ] Test 5: Release sequence (5 frames) works
- [ ] Test 6: Confidence < 0.60 → "Uncertain"
- [ ] Test 7: Null label → "No clear sign"
- [ ] Test 8: 45-frame grace visible in logs
- [ ] No JavaScript console errors
- [ ] No Python errors in backend logs
- [ ] No random/stale words showing

---

## If Any Test Fails

**Check these immediately:**

1. **Backend logs** for `[ERROR]` or `[WARN]` messages
2. **Browser console** (F12) for red error messages
3. **Network tab** (F12) for WebSocket connection status
4. **Response JSON** - are all required fields present?
5. **asl_capture_state** values - are they lowercase and correct?

**Common issues:**

- Ring color stays wrong → Check `asl_capture_state` in response (should be "ready", "capturing", "predicting", "wait_for_release")
- Prediction repeats → Check if state transitions to "wait_for_release"
- Camera OFF doesn't reset → Check if `camera_on` field is being sent from frontend
- 45/35 mismatch → Check if downsampling code runs in `_handle_predicting()`

---

## Submit Results

Once you've run the tests, paste your results here with:
1. Which tests passed ✓
2. Which tests failed ✗
3. Any error messages
4. Backend log snippets for failures

Then we can fix any remaining issues before commit.
