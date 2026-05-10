import "../css/CaptionsPanel.css";

function CaptionsPanel({
  aslEnabled,
  showCaptions,
  prediction,
  status,
  confidence,
  handsCount,
  modelName,
  inferenceDevice,
  inferenceMode,
  manualMode = false,
  manualCaptureState = "manual_ready",
  countdownMs = 0,
  cameraOn = true,
  onToggleManualMode,
  onStartManualCapture,
  onCancelManualCapture,
}) {
  const REQUIRED_FRAMES = 35;

  const isCountingDown = countdownMs > 0;
  const isCapturing = manualCaptureState === "manual_capturing";
  const isPredicting = manualCaptureState === "manual_predicting";
  const isResult = manualCaptureState === "manual_result";
  // Busy = cannot start a new capture (but manual_result allows R/button)
  const isBusy = isCountingDown || isCapturing || isPredicting;

  // Parse captured frame progress from status string e.g. "Manual | capturing 12/45"
  let frameProgress = 0;
  if (isCapturing && status) {
    const match = status.match(/capturing\s+(\d+)\/(\d+)/i);
    if (match) frameProgress = parseInt(match[1], 10);
  }

  function getManualButtonLabel() {
    if (!cameraOn) return "Camera Off";
    if (isCountingDown) return `Get ready… ${(countdownMs / 1000).toFixed(1)}s`;
    if (isCapturing) return `Capturing (${frameProgress}/${REQUIRED_FRAMES})`;
    if (isPredicting) return "Processing…";
    if (isResult) return "Capture Again (R)";
    return "Start Sign Capture (R)";
  }

  function getManualStateLabel() {
    if (!cameraOn) return "—";
    if (isCountingDown) return "Get ready…";
    if (isCapturing) return `Capturing frames: ${frameProgress} / ${REQUIRED_FRAMES}`;
    if (isPredicting) return "Running prediction…";
    if (isResult) return "Result ready";
    return "Ready";
  }

  return (
    <div className="panel-content">
      <div className="status-chip">
        {aslEnabled ? "Translator ON" : "Translator OFF"}
      </div>

      {/* ── Manual Mode Toggle ── */}
      <div className="manual-mode-row">
        <span className="manual-mode-label">Manual Capture Mode</span>
        <button
          id="toggle-manual-mode"
          className={`manual-toggle-btn ${manualMode ? "active" : ""}`}
          onClick={onToggleManualMode}
          title="Toggle manual capture mode (press R to capture)"
        >
          {manualMode ? "ON" : "OFF"}
        </button>
      </div>

      {/* ── Manual Capture Controls (only when manual mode is on) ── */}
      {manualMode && (
        <div className="manual-capture-block">
          <div className="manual-state-label">{getManualStateLabel()}</div>

          {/* Progress bar */}
          {isCapturing && (
            <div className="manual-progress-bar-track">
              <div
                className="manual-progress-bar-fill"
                style={{ width: `${Math.round((frameProgress / REQUIRED_FRAMES) * 100)}%` }}
              />
            </div>
          )}

          <div className="manual-btn-row">
            <button
              id="start-manual-capture"
              className={`manual-capture-btn ${isBusy ? "disabled" : ""}`}
              onClick={onStartManualCapture}
              disabled={!cameraOn || isBusy}
              title="Start manual sign capture (keyboard: R)"
            >
              {getManualButtonLabel()}
            </button>

            {isBusy && (
              <button
                id="cancel-manual-capture"
                className="manual-cancel-btn"
                onClick={onCancelManualCapture}
                title="Cancel capture (keyboard: Escape)"
              >
                Cancel
              </button>
            )}
          </div>

          <div className="manual-hint">
            {cameraOn
              ? "Press R or the button to start a 1-second countdown, then record 35 frames."
              : "Turn on your camera to use manual capture."}
          </div>
        </div>
      )}

      <div className="info-box">
        <div className="info-label">Latest recognized sign</div>
        <div className="info-value">{showCaptions ? prediction : "Hidden"}</div>
      </div>

      <div className="info-box">
        <div className="info-label">Recognition status</div>
        <div className="info-value small">{status}</div>
      </div>

      <div className="info-box">
        <div className="info-label">Confidence</div>
        <div className="info-value small">{confidence.toFixed(2)}</div>
      </div>

      <div className="info-box">
        <div className="info-label">Hands detected (frame)</div>
        <div className="info-value small">{handsCount}</div>
      </div>

      <div className="info-box">
        <div className="info-label">Model name</div>
        <div className="info-value small">{modelName}</div>
      </div>

      <div className="info-box">
        <div className="info-label">Inference device</div>
        <div className="info-value small">{inferenceDevice}</div>
      </div>

      <div className="info-box">
        <div className="info-label">Inference mode</div>
        <div className="info-value small">{inferenceMode}</div>
      </div>

      <div className="helper-text">
        Your React UI is sending camera frames to the Python backend. The backend
        runs MediaPipe + your phrase model and returns live prediction data here.
      </div>
    </div>
  );
}

export default CaptionsPanel;
